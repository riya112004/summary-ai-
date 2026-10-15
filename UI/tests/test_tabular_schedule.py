import json
import unittest
from datetime import date

from plan_intelligence import (
    build_plan_tasks,
    build_tabular_schedule_summary,
    serialize_plan_schedule,
)


class TabularScheduleSummaryTests(unittest.TestCase):
    def test_returns_sorted_entries_for_today_and_marks_meetings(self):
        text = """schedule_date | weekday | start_time | end_time | activity | category | details | location | priority | status
2026-10-14 | Wednesday | 10:45 AM | 11:30 AM | Client project review meeting | Meeting | Discuss progress | Video call | High | Planned
2026-10-14 | Wednesday | 06:00 AM | 06:20 AM | Wake up and get ready | Personal routine | Start the day | Home | Medium | Planned
2026-10-15 | Thursday | 09:00 AM | 10:00 AM | Future appointment | Appointment | Follow up | Clinic | High | Planned
"""

        schedule = build_tabular_schedule_summary(
            text,
            today=date(2026, 10, 14),
        )

        self.assertIsNotNone(schedule)
        self.assertEqual(schedule["today"]["focus"], "Wake up and get ready")
        self.assertEqual(
            [entry["activity"] for entry in schedule["entries"]],
            ["Wake up and get ready", "Client project review meeting"],
        )
        self.assertTrue(schedule["entries"][1]["is_meeting"])
        self.assertEqual(schedule["entries"][1]["start_minute"], 645)
        self.assertEqual(schedule["entries"][1]["end_minute"], 690)
        json.dumps(serialize_plan_schedule(schedule))

    def test_supports_next_day_time_and_rejects_non_schedule_tables(self):
        schedule = build_tabular_schedule_summary(
            """date | title | start | end
2026-10-14 | Sleep | 10:00 PM | 06:00 AM (next day)
""",
            today=date(2026, 10, 14),
        )
        self.assertEqual(schedule["entries"][0]["end_minute"], 1800)
        self.assertIsNone(build_tabular_schedule_summary(
            "name | amount\nTest | 100\n",
            today=date(2026, 10, 14),
        ))

    def test_creates_persistent_task_records_for_every_schedule_row(self):
        text = """schedule_date | start_time | end_time | activity | category | details | location | priority | status
2026-10-14 | 06:00 AM | 06:20 AM | Morning routine | Personal routine | Get ready | Home | Medium | Planned
2026-10-14 | 10:45 AM | 11:30 AM | Client meeting | Meeting | Review progress | Video call | High | Planned
2026-10-15 | 09:00 AM | 09:30 AM | Submit report | Work | Send final report | Office | High | Planned
"""

        tasks = build_plan_tasks(text, "plan-123")

        self.assertEqual(len(tasks), 3)
        self.assertEqual([task["title"] for task in tasks], [
            "Morning routine",
            "Client meeting",
            "Submit report",
        ])
        self.assertEqual(
            [task["task_type"] for task in tasks],
            ["csv_schedule", "csv_schedule", "csv_schedule"],
        )
        self.assertEqual(tasks[0]["due_date"], "2026-10-14")
        self.assertIn("Time: 06:00 AM–06:20 AM", tasks[0]["description"])
        self.assertNotEqual(tasks[0]["source_key"], tasks[1]["source_key"])
        extended = build_plan_tasks(
            text.replace(
                "2026-10-14 | 06:00 AM",
                "2026-10-13 | 05:00 AM | 05:30 AM | Earlier task | Work | Prepare | Office | Low | Planned\n"
                "2026-10-14 | 06:00 AM",
            ),
            "plan-123",
        )
        self.assertEqual(
            tasks[0]["source_key"],
            next(task["source_key"] for task in extended if task["title"] == "Morning routine"),
        )


if __name__ == "__main__":
    unittest.main()
