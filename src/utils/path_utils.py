import time
import random

def get_scene_asset_name(index, asset_type="image", prefix="grok", extension=None):
    """
    씬 인덱스를 포함한 정형화된 파일 이름을 생성합니다.
    
    Args:
        index (int): 씬 인덱스 (0, 1, 2...)
        asset_type (str): "image" 또는 "video"
        prefix (str): "grok", "nano", "original" 등
        extension (str): 확장자 (예: "png", "mp4"). None이면 기본값 사용.
        
    Returns:
        str: 생성된 파일 이름
    """
    timestamp = int(time.time() * 1000)
    random_hex = f"{random.getrandbits(32):x}"
    
    if extension is None:
        extension = "mp4" if asset_type == "video" else "png"
    
    if asset_type == "video":
        # grok_video_scene_0_1710300000.mp4
        return f"{prefix}_video_scene_{index}_{timestamp}.{extension}"
    else:
        # grok_scene_0_1710300000_abcd1234.png
        return f"{prefix}_scene_{index}_{timestamp}_{random_hex}.{extension}"

def get_scene_pattern(index, asset_type="image"):
    """
    특정 씬의 파일을 찾기 위한 glob 패턴을 반환합니다.
    """
    if asset_type == "video":
        return f"*_video_scene_{index}_*.mp4"
    else:
        return f"*_scene_{index}_*.*"
