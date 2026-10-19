import unittest

from main import _task_sort_key


class TaskOrderingTests(unittest.TestCase):
    def test_tasks_are_ordered_by_date_and_start_time(self):
        tasks = [
            {"due_date": "2026-10-16", "start_time": "11:30", "title": "Meeting"},
            {"due_date": "2026-10-16", "start_time": "07:30", "title": "Breakfast"},
            {"due_date": "2026-10-16", "start_time": "07:00", "title": "Morning reset"},
            {"due_date": "2026-10-15", "start_time": "12:00", "title": "Yesterday"},
            {"due_date": "2026-10-16", "start_time": "", "title": "Unscheduled"},
        ]

        tasks.sort(key=_task_sort_key)

        self.assertEqual(
            [task["title"] for task in tasks],
            ["Yesterday", "Morning reset", "Breakfast", "Meeting", "Unscheduled"],
        )

    def test_am_pm_and_24_hour_times_share_chronological_order(self):
        tasks = [
            {"due_date": "2026-10-16", "start_time": "1:00 PM", "title": "Afternoon"},
            {"due_date": "2026-10-16", "start_time": "07:00", "title": "Morning"},
            {"due_date": "2026-10-16", "start_time": "12:00 PM", "title": "Noon"},
        ]

        tasks.sort(key=_task_sort_key)

        self.assertEqual(
            [task["title"] for task in tasks],
            ["Morning", "Noon", "Afternoon"],
        )


if __name__ == "__main__":
    unittest.main()
