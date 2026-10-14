import os
import queue
from pathlib import Path
from typing import List, Tuple, Callable, Optional

# DTO Layer
from core.models import VideoTask
# Domain Logic
from automation.minimax_h3 import MinimaxH3Client
from utils.path_utils import get_scene_asset_name


class VideoService:
    """
    MiniMax H3 (RTX 4060 Ti 최적화) 비디오 생성 비즈니스 로직을 담당하는 Service 클래스.
    GPU VRAM 한계(8GB)를 고려하여 단일 큐 순차 처리(Sequential Queue)를 엄격히 보장합니다.
    """

    @staticmethod
    def get_client(base_url: str = "http://127.0.0.1:8188") -> MinimaxH3Client:
        return MinimaxH3Client(base_url=base_url)

    @staticmethod
    def check_connection(base_url: str = "http://127.0.0.1:8188") -> bool:
        return MinimaxH3Client(base_url=base_url).check_connection()

    @staticmethod
    def generate_single_video(
        task: VideoTask,
        base_url: str = "http://127.0.0.1:8188",
        output_dir: str = "temp_videos",
        progress_callback: Optional[Callable[[float, str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> Optional[str]:
        """
        단일 VideoTask에 대해 이미지를 업로드하고 비디오를 생성 및 다운로드합니다.
        
        :param task: VideoTask 인스턴스 (idx, image_path, motion_prompt, workflow_key)
        :param base_url: ComfyUI 서버 URL
        :param output_dir: 저장할 디렉토리 (기본 temp_videos)
        :return: 생성된 비디오의 로컬 파일 경로 (실패 시 None)
        """
        client = MinimaxH3Client(base_url=base_url)
        img_path = Path(task.image_path)
        if not img_path.exists():
            print(f"[VideoService] Scene {task.idx} 이미지 파일이 존재하지 않습니다: {img_path}")
            return None

        # 1. 템플릿 경로 확인
        workflow_key = getattr(task, "workflow_key", "character_fast") or "character_fast"
        template_path = client.get_template_path(workflow_key)

        # 2. 이미지 업로드 (안전한 영문 파일명으로 ComfyUI에 전송)
        uploaded_name = client.upload_image(img_path, scene_index=task.idx)

        # 3. 비디오 생성 (폴링 대기)
        output_prefix = f"video/ShortsMaker/scene_{task.idx:03d}"
        video_meta = client.generate_shorts(
            template_api_json_path=template_path,
            image_name=uploaded_name,
            prompt=task.motion_prompt or "Cinematic motion",
            output_prefix=output_prefix,
            timeout_seconds=240,
            progress_callback=progress_callback,
            stop_check=stop_check
        )

        # 4. 결과 비디오 로컬 경로 다운로드
        os.makedirs(output_dir, exist_ok=True)
        local_filename = get_scene_asset_name(task.idx, asset_type="video", prefix="minimax")
        save_path = Path(output_dir) / local_filename

        client.download_video(video_meta, save_path)
        return str(save_path.resolve())

    @staticmethod
    def generate_videos_parallel(
        tasks: List[VideoTask],
        max_workers: int = 1,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        on_task_done: Optional[Callable[[int, str], None]] = None,
        base_url: str = "http://127.0.0.1:8188",
        output_dir: str = "temp_videos"
    ) -> List[Tuple[int, Optional[str]]]:
        """
        다수의 VideoTask 작업을 처리합니다.
        [RTX 4060 Ti 최적화]: VRAM(8GB) OOM 방지를 위해 max_workers와 상관없이
        단일 순차 실행(Sequential)으로 1개씩 안전하게 생성합니다.
        
        :param tasks: 실행할 VideoTask 리스트
        :param max_workers: 레거시 호환용 파라미터 (내부적으로 1개씩 순차 처리)
        :param progress_callback: 전체 진행률 콜백 (completed, total, message)
        :param stop_check: 중단 여부 확인 콜백
        :param on_task_done: 각 씬 완료 시 실시간 호출되는 콜백 (idx, video_path)
        :return: (작업 인덱스, 비디오 경로)의 리스트
        """
        if not tasks:
            return []

        results = []
        total = len(tasks)
        completed_count = 0

        # 서버 연결 사전 확인
        client = MinimaxH3Client(base_url=base_url)
        if not client.check_connection():
            raise ConnectionError(f"ComfyUI 서버({base_url})에 연결할 수 없습니다. ComfyUI를 먼저 실행해 주세요.")

        for task in tasks:
            if stop_check and stop_check():
                print(f"[VideoService] 중단 요청 확인. 남은 {total - completed_count}개 작업을 생략합니다.")
                break

            print(f"[VideoService] Scene {task.idx} 비디오 변환 시작 (총 {total}개 중 {completed_count + 1}번째)...")

            # 단일 씬 진행 안내 콜백
            def single_scene_progress(elapsed_sec: float, msg: str):
                if progress_callback:
                    progress_callback(
                        completed_count,
                        total,
                        f"🎬 Scene {task.idx + 1}/{total} 렌더링 중... ({int(elapsed_sec)}초 경과)"
                    )

            video_path = None
            try:
                video_path = VideoService.generate_single_video(
                    task=task,
                    base_url=base_url,
                    output_dir=output_dir,
                    progress_callback=single_scene_progress,
                    stop_check=stop_check
                )
            except InterruptedError:
                print(f"[VideoService] Scene {task.idx} 사용자 중단.")
                break
            except Exception as e:
                print(f"[VideoService] Scene {task.idx} 생성 실패: {e}")
                video_path = None

            results.append((task.idx, video_path))
            completed_count += 1

            if on_task_done:
                on_task_done(task.idx, video_path)

            if progress_callback:
                progress_callback(
                    completed_count,
                    total,
                    f"🎬 영상 제작 진행 중... ({completed_count}/{total})"
                )

        return sorted(results, key=lambda x: x[0])

    @staticmethod
    def process_video_queue(
        task_queue,  # queue.Queue instance
        on_task_completed: Callable[[int, Optional[str]], None],
        stop_check: Optional[Callable[[], bool]] = None,
        base_url: str = "http://127.0.0.1:8188",
        output_dir: str = "temp_videos"
    ):
        """
        [원스톱 파이프라인] 큐에서 VideoTask를 하나씩 꺼내어 순차 처리하는 워커입니다.
        RTX 4060 Ti VRAM 보호를 위해 단 1개의 워커 스레드로 동작합니다.
        """
        print(f"[VideoService] 원스톱 비디오 워커 스레드 시작 (ComfyUI: {base_url})")

        while True:
            if stop_check and stop_check():
                print("[VideoService] 워커 중단 신호 감지")
                break

            try:
                task = task_queue.get(timeout=3)
            except queue.Empty:
                continue
            try:
                if task is None:  # 종료 신호 (Sentinel)
                    print("[VideoService] 워커 종료 신호 수신")
                    break

                print(f"[VideoService] 큐 작업 시작: Scene {task.idx}")
                video_path = None
                try:
                    video_path = VideoService.generate_single_video(
                        task=task,
                        base_url=base_url,
                        output_dir=output_dir,
                        stop_check=stop_check
                    )
                except Exception as e:
                    print(f"[VideoService] 큐 작업 실패 (Scene {task.idx}): {e}")
                    video_path = None

                on_task_completed(task.idx, video_path)
            finally:
                task_queue.task_done()
