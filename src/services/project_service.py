import os
import json
import base64
import requests
import glob
import tempfile
try:
    from utils.path_utils import get_scene_asset_name, get_scene_pattern
except ImportError:
    from src.utils.path_utils import get_scene_asset_name, get_scene_pattern

class ProjectService:
    @staticmethod
    def save_project_draft(scenes):
        """현재 세션의 scenes 상태를 파일로 저장하여 새로고침 시에도 유지되도록 합니다."""
        temp_path = None
        try:
            draft_path = "config/project_draft.json"
            os.makedirs("config", exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir="config", delete=False) as f:
                temp_path = f.name
                json.dump(scenes, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, draft_path)
        except Exception as e:
            raise RuntimeError(f"프로젝트 저장 실패 (기존 저장본 유지): {e}") from e
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def load_project_draft():
        """저장된 프로젝트 드래프트가 있다면 불러옵니다."""
        draft_path = "config/project_draft.json"
        if os.path.exists(draft_path) and os.path.getsize(draft_path) > 0:
            try:
                with open(draft_path, "r", encoding="utf-8") as f:
                    scenes = json.load(f)
                    # [이개발의 팁] 순서가 섞이지 않도록 ID 기준으로 정렬합니다.
                    return sorted(scenes, key=lambda x: x.get('id', 0))
            except Exception as e:
                print(f"Error loading project draft: {e}")
        return None

    @staticmethod
    def save_image_asset(image_data, prefix="grok", idx=0):
        """URL, base64, bytes, 파일명 중 하나를 받아 temp_images에 저장하고 절대경로를 반환합니다."""
        if not os.path.exists("temp_images"):
            os.makedirs("temp_images")

        filename = get_scene_asset_name(idx, "image", prefix)
        filepath = os.path.abspath(os.path.join("temp_images", filename))

        try:
            if isinstance(image_data, str):
                if image_data.startswith("http"):
                    # URL인 경우
                    response = requests.get(image_data)
                    if response.ok:
                        with open(filepath, "wb") as f:
                            f.write(response.content)
                        return filepath
                elif image_data.startswith("data:"):
                    # base64인 경우
                    header, encoded = image_data.split(",", 1)
                    data = base64.b64decode(encoded)
                    with open(filepath, "wb") as f:
                        f.write(data)
                    return filepath
                elif os.path.exists(image_data):
                    # 파일 경로인 경우 (그대로 반환)
                    return os.path.abspath(image_data)
            elif isinstance(image_data, bytes):
                # bytes인 경우
                with open(filepath, "wb") as f:
                    f.write(image_data)
                return filepath
        except Exception as e:
            print(f"Error saving image: {e}")

        return None

    @staticmethod
    def auto_restore_assets(scenes):
        """
        [Clean Architecture] 인덱스 기반 파일명을 활용해 유실된 에셋 연결을 자동 복구합니다.
        Memory-efficient: 파일 내용이 아닌 경로만 스캔합니다.
        """
        if not scenes: return
        
        for idx, scene in enumerate(scenes):
            # 1. 이미지 복구 (image_path가 없거나 파일이 유실된 경우)
            if not scene.get('image_path') or not os.path.exists(scene['image_path']):
                pattern = get_scene_pattern(idx, "image")
                matches = sorted(glob.glob(os.path.join("temp_images", pattern)))
                if matches:
                    scene['image_path'] = os.path.abspath(matches[-1])
                    print(f"[AutoRestore] Scene {idx} image restored: {scene['image_path']}")

            # 2. 비디오 복구
            if not scene.get('video_path') or not os.path.exists(scene['video_path']):
                pattern = get_scene_pattern(idx, "video")
                matches = sorted(glob.glob(os.path.join("outputs", pattern)))
                if matches:
                    scene['video_path'] = os.path.abspath(matches[-1])
                    print(f"[AutoRestore] Scene {idx} video restored: {scene['video_path']}")
