from unittest import mock

from src.shared import cpu_threads


def test_explicit_budget_and_disable():
    assert cpu_threads.resolve_cpu_thread_budget({"SABER_CPU_THREADS": "3"}) == 3
    assert cpu_threads.resolve_cpu_thread_budget({"SABER_CPU_THREADS": "0"}) is None


def test_auto_budget_is_half_of_physical_cores_clamped():
    with mock.patch.object(cpu_threads, "_physical_cores", return_value=12):
        assert cpu_threads.resolve_cpu_thread_budget({}) == 6
    with mock.patch.object(cpu_threads, "_physical_cores", return_value=2):
        assert cpu_threads.resolve_cpu_thread_budget({}) == 2
    with mock.patch.object(cpu_threads, "_physical_cores", return_value=32):
        assert cpu_threads.resolve_cpu_thread_budget({}) == 6


def test_configure_sets_torch_threads_on_cpu_only_machine():
    import torch

    original = torch.get_num_threads()
    try:
        with mock.patch("torch.cuda.is_available", return_value=False), \
                mock.patch.object(cpu_threads, "_lower_process_priority") as lower:
            budget = cpu_threads.configure_cpu_threads(
                {"SABER_CPU_THREADS": "2", "SABER_CPU_LOW_PRIORITY": "0"}
            )
        assert budget == 2
        assert torch.get_num_threads() == 2
        lower.assert_not_called()
    finally:
        torch.set_num_threads(original)
