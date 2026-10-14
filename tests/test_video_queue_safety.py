import queue
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core.models import VideoTask
from services.video_service import VideoService


class VideoQueueSafetyTests(unittest.TestCase):
    def test_failed_generation_reports_failure_and_finishes_queue(self):
        jobs = queue.Queue()
        jobs.put(VideoTask(0, 'image.png', 'motion'))
        jobs.put(None)
        callback = Mock()
        with patch.object(VideoService, 'generate_single_video', side_effect=RuntimeError('render failed')):
            VideoService.process_video_queue(jobs, callback)
        callback.assert_called_once_with(0, None)
        self.assertEqual(jobs.unfinished_tasks, 0)

    def test_callback_failure_propagates_and_releases_task(self):
        jobs = queue.Queue()
        jobs.put(VideoTask(0, 'image.png', 'motion'))
        with patch.object(VideoService, 'generate_single_video', return_value='video.mp4'):
            with self.assertRaisesRegex(RuntimeError, 'save failed'):
                VideoService.process_video_queue(jobs, Mock(side_effect=RuntimeError('save failed')))
        self.assertEqual(jobs.unfinished_tasks, 0)

    def test_only_empty_queue_is_retried(self):
        jobs = Mock()
        jobs.get.side_effect = [queue.Empty, RuntimeError('queue broken')]
        with self.assertRaisesRegex(RuntimeError, 'queue broken'):
            VideoService.process_video_queue(jobs, Mock())
        self.assertEqual(jobs.get.call_count, 2)


if __name__ == '__main__':
    unittest.main()
