import json
import random
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import requests

# 워크플로우 템플릿 기본 위치
WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "resources" / "workflows"

WORKFLOW_PRESETS: Dict[str, Dict[str, Any]] = {
    "character_fast": {
        "name": "H3 캐릭터/애니메이션 (LightUpscale Fast)",
        "file_name": "H3_SetB_Character_LightUpscale_Fast.api.json",
        "estimated_time": "약 80초",
        "description": "H3_SetB 기반 캐릭터 및 애니메이션 모션 최적화 (LightUpscale Fast)"
    },
    "real_person_natural": {
        "name": "H3 인물 실사화 최적화 (Real Person Natural)",
        "file_name": "H3_RealPerson_Natural_Optimized.api.json",
        "estimated_time": "약 90초",
        "description": "실사 인물 피부 질감 및 자연스러운 인물 움직임에 최적화"
    }
}


class MinimaxH3Client:
    """
    ComfyUI 기반 MiniMax H3 (RTX 4060 Ti 최적화) 비디오 생성 클라이언트.
    HTTP API를 통해 단일 GPU 큐를 안전하게 제어합니다.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8188"):
        self.base_url = base_url.rstrip("/")

    def check_connection(self, timeout: float = 3.0) -> bool:
        """ComfyUI 서버가 8188 포트에서 실행 중인지 확인합니다."""
        try:
            res = requests.get(f"{self.base_url}/system_stats", timeout=timeout)
            return res.status_code == 200
        except Exception:
            return False

    def interrupt_current(self):
        """현재 ComfyUI에서 실행 중인 큐 작업을 즉시 중단 요청합니다."""
        try:
            requests.post(f"{self.base_url}/interrupt", timeout=2.0)
        except Exception:
            pass

    def upload_image(self, image_path: Path, scene_index: int = 0) -> str:
        """
        쇼츠의 시작 이미지를 ComfyUI 서버로 업로드합니다.
        한글/특수문자 경로 오류를 방지하기 위해 파일명을 안전한 영문으로 매핑합니다.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"업로드할 이미지를 찾을 수 없습니다: {image_path}")

        url = f"{self.base_url}/upload/image"
        ext = image_path.suffix.lstrip(".") or "png"
        safe_name = f"input_scene_{scene_index:03d}_{int(time.time() * 1000)}.{ext}"

        with open(image_path, "rb") as f:
            files = {"image": (safe_name, f, f"image/{ext}")}
            data = {"overwrite": "true"}
            res = requests.post(url, files=files, data=data, timeout=30)
            res.raise_for_status()
            res_data = res.json()
            return res_data.get("name", safe_name)

    def get_template_path(self, workflow_key: str = "character_fast") -> Path:
        """프리셋 키에 해당하는 API 템플릿 JSON 경로를 반환합니다."""
        preset = WORKFLOW_PRESETS.get(workflow_key, WORKFLOW_PRESETS["character_fast"])
        path = WORKFLOWS_DIR / preset["file_name"]
        if not path.exists():
            raise FileNotFoundError(f"워크플로우 템플릿 파일을 찾을 수 없습니다: {path}")
        return path

    def generate_shorts(
        self,
        template_api_json_path: Path,
        image_name: str,
        prompt: str,
        output_prefix: str = "video/ShortsMaker/shorts",
        seed: Optional[int] = None,
        timeout_seconds: int = 240,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> dict:
        """
        MiniMax H3 비디오 생성을 요청하고 완료될 때까지 대기한 후 결과 비디오 정보를 반환합니다.
        
        :param template_api_json_path: API JSON 워크플로우 경로
        :param image_name: upload_image를 통해 반환된 ComfyUI 내 이미지 이름
        :param prompt: 모션 및 장면 묘사 프롬프트
        :param output_prefix: 저장될 폴더 및 파일명 접두사 (예: video/ShortsMaker/scene_001)
        :param seed: 난수 시드 (None이면 자동 무작위 생성)
        :param timeout_seconds: 최대 대기 시간 (기본 240초)
        :param progress_callback: UI 업데이트용 콜백 (진행초/예상초, 메시지)
        :param stop_check: 중단 여부 확인 콜백
        """
        # 1. 템플릿 로드
        with open(template_api_json_path, "r", encoding="utf-8") as f:
            graph = json.load(f)

        if seed is None:
            seed = random.randint(100000000000000, 999999999999999)

        # 2. 파라미터 주입 (Node 19: Image, Node 6: Prompt, Node 10: Seed, Node 15: Output Prefix)
        if "19" in graph and "image" in graph["19"].get("inputs", {}):
            graph["19"]["inputs"]["image"] = image_name
        if "6" in graph and "prompt" in graph["6"].get("inputs", {}):
            graph["6"]["inputs"]["prompt"] = prompt
        if "10" in graph and "noise_seed" in graph["10"].get("inputs", {}):
            graph["10"]["inputs"]["noise_seed"] = seed
        if "15" in graph and "filename_prefix" in graph["15"].get("inputs", {}):
            graph["15"]["inputs"]["filename_prefix"] = output_prefix

        # 3. 큐에 등록 (POST /prompt)
        prompt_res = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": graph},
            timeout=30
        )
        prompt_res.raise_for_status()
        prompt_id = prompt_res.json().get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI에서 prompt_id를 반환하지 않았습니다: {prompt_res.text}")

        print(f"[MiniMax H3] 생성 시작 - Task ID: {prompt_id} (Seed: {seed})")

        # 4. 폴링 대기 루프
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            # 중단 요청 확인
            if stop_check and stop_check():
                print(f"[MiniMax H3] 사용자 중단 요청 감지. 작업을 취소합니다. (ID: {prompt_id})")
                self.interrupt_current()
                raise InterruptedError("사용자에 의해 비디오 생성이 중단되었습니다.")

            elapsed = int(time.time() - start_time)
            if progress_callback:
                progress_callback(elapsed, f"🎬 MiniMax H3 렌더링 중... ({elapsed}초 경과)")

            try:
                history_res = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
                history_data = history_res.json()
            except Exception as e:
                # 순간적인 네트워크 지연일 수 있으므로 재시도
                print(f"[MiniMax H3] 상태 확인 중 일시 오류: {e}")
                time.sleep(2)
                continue

            if prompt_id in history_data:
                item = history_data[prompt_id]
                # 오류 발생 여부 확인
                if item.get("status", {}).get("status_str") == "error":
                    messages = item.get("status", {}).get("messages", [])
                    raise RuntimeError(f"ComfyUI 생성 오류: {messages}")

                # 노드 15 출력 확인 (SaveVideo)
                outputs = item.get("outputs", {})
                if "15" in outputs:
                    out_15 = outputs["15"]
                    if "videos" in out_15 and len(out_15["videos"]) > 0:
                        video_info = out_15["videos"][0]
                        total_elapsed = round(time.time() - start_time, 1)
                        print(f"[MiniMax H3] 생성 성공! ({total_elapsed}초 소요)")
                        return video_info
                    elif "images" in out_15 and len(out_15["images"]) > 0:
                        video_info = out_15["images"][0]
                        total_elapsed = round(time.time() - start_time, 1)
                        print(f"[MiniMax H3] 생성 성공! ({total_elapsed}초 소요)")
                        return video_info

            time.sleep(2)

        raise TimeoutError(f"{timeout_seconds}초 동안 비디오 생성이 완료되지 않았습니다.")

    def download_video(self, video_info: dict, save_to: Path) -> Path:
        """생성된 비디오를 프로젝트 로컬 경로로 스트리밍 다운로드합니다."""
        save_to = Path(save_to)
        save_to.parent.mkdir(parents=True, exist_ok=True)

        params = {
            "filename": video_info["filename"],
            "subfolder": video_info.get("subfolder", ""),
            "type": video_info.get("type", "output")
        }
        res = requests.get(f"{self.base_url}/view", params=params, stream=True, timeout=60)
        res.raise_for_status()

        with open(save_to, "wb") as f:
            for chunk in res.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        print(f"[MiniMax H3] 다운로드 완료: {save_to}")
        return save_to
