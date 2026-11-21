# A2A integration tests (2026-11-20)

Every test runs on a temporary bus file (`tests/conftest.py`). No model call, no network. Results are from `pytest tests/test_a2a.py` (12 passed) and the two agenteval mutation tests in `tests/test_agents_training.py` (pass).

| Workflow asked for | What tests it | Result |
|---|---|---|
| Research → Script | Existing: `tests/test_grounding.py` (the source reaches the writer; a script without a source is flagged) | pass (suite) |
| Script → Fact check | Existing: `tests/test_scriptreview.py`, `test_grounding` (`verify_and_revise`) | pass |
| Fact check → Script correction | Existing: `scriptgen.verify_and_revise` tests (flagged lines rewritten from the sources before refusal) | pass |
| Script → Voice | `test_stage_hand_overs_check_the_real_output_and_record_it` (script contract), `test_a_script_with_broken_chapters_is_refused` | pass |
| Script → Visual | Same test: 8 lines need 8 picture files; one missing file is refused | pass |
| Voice + Visual → Render | Same test: a cut narration (9 s video for 16 s of voice) is refused; within tolerance it passes. `test_the_documentary_producer_checks_every_stage_in_order`: the producer calls all four checks in order, and the render check comes before the record is saved. | pass |
| Render → Review | `tests/test_render_concat.py` (real ffmpeg, a GIF named .jpg); reviewer tests | pass |
| Review → Fixer and Fixer → Review | `test_only_the_target_takes_and_answers_and_a_closed_task_is_never_completed_twice` (fixer asks the reviewer; only the reviewer answers; a late second answer is refused); existing `tests/test_fixer*.py` | pass |
| Doctor → Autopilot recovery | `test_an_agent_cannot_message_itself_or_an_agent_off_its_hand_over_map` (the doctor may ask anyone); `test_only_the_sender_or_the_doctor_cancels`; existing doctor tests | pass |
| Failure: invalid answer | `test_a_wrong_answer_is_asked_again_then_the_task_fails` | pass |
| Failure: timeout | `test_a_task_past_its_deadline_is_offered_again_then_failed` | pass |
| Duplicate message | `test_send_makes_one_bus_task_and_a_repeat_is_the_same_task` | pass |
| Injection | `test_text_is_cleaned_and_stored_as_data` | pass |
| Owner-only actions unreachable | `test_no_a2a_path_reaches_an_owner_only_action` | pass |
| Agent checks | agenteval `case_an_a2a_task_is_answered_once_only_by_its_target_and_never_off_the_hand_over_map`. Mutations: a done task counted as live is caught (`twice=True`); ignoring the hand-over map is caught (`off_map=False`). | pass |

**Not tested live:** no real video was made today through the new hand-over checks. Free text models are rate-limited upstream (see `END_TO_END_VIDEO_TEST.md`).
