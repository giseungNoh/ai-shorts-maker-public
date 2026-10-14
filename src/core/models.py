from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class VideoTask:
    """
    비디오 생성 작업을 정의하는 Data Transfer Object (DTO)
    UI 레이어(main.py)에서 생성된 후 Service 레이어로 전달되어,
    session_state 의존성을 제거하고 데이터 접근을 명확히 합니다.
    """
    idx: int
    image_path: str
    motion_prompt: str
    workflow_key: str = "character_fast"  # 'character_fast' or 'real_person_natural'
    account: Dict[str, Any] = None  # 레거시 호환용 필드
    headless: bool = True           # 레거시 호환용 필드
