import pytest
import threading
import time
from pathlib import Path
import config_manager


def test_edit_config_success(tmp_path, monkeypatch):
    # Set up temp config path
    tmp_config_file = tmp_path / "test_config.json"
    monkeypatch.setattr(config_manager, "CONFIG_PATH", tmp_config_file)
    
    # Initialize config
    config_manager.ensure_config()
    
    # Modify config using context manager
    with config_manager.edit_config() as config:
        config["journals"].append({"id": "j1", "name": "Journal 1"})
        
    # Read back and verify
    read_config = config_manager.load_config()
    assert len(read_config["journals"]) == 1
    assert read_config["journals"][0]["name"] == "Journal 1"


def test_edit_config_rollback_on_exception(tmp_path, monkeypatch):
    # Set up temp config path
    tmp_config_file = tmp_path / "test_config.json"
    monkeypatch.setattr(config_manager, "CONFIG_PATH", tmp_config_file)
    
    # Initialize config
    config_manager.ensure_config()
    
    # Try modifying config but raise exception
    with pytest.raises(ValueError):
        with config_manager.edit_config() as config:
            config["journals"].append({"id": "j2", "name": "Journal 2"})
            raise ValueError("Something went wrong")
            
    # Read back and verify that the change was NOT saved
    read_config = config_manager.load_config()
    assert len(read_config["journals"]) == 0


def test_edit_config_concurrent_lock(tmp_path, monkeypatch):
    # Set up temp config path
    tmp_config_file = tmp_path / "test_config.json"
    monkeypatch.setattr(config_manager, "CONFIG_PATH", tmp_config_file)
    
    config_manager.ensure_config()
    
    order = []
    
    def thread_1_work():
        with config_manager.edit_config() as config:
            order.append("t1_start")
            time.sleep(0.2)
            config["journals"].append({"id": "t1", "name": "T1"})
            order.append("t1_end")
            
    def thread_2_work():
        # wait a tiny bit to ensure thread 1 gets lock first
        time.sleep(0.05)
        with config_manager.edit_config() as config:
            order.append("t2_start")
            config["journals"].append({"id": "t2", "name": "T2"})
            order.append("t2_end")
            
    t1 = threading.Thread(target=thread_1_work)
    t2 = threading.Thread(target=thread_2_work)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    # Since thread 1 holds the lock for 0.2s, thread 2's start MUST be after thread 1's end
    assert order == ["t1_start", "t1_end", "t2_start", "t2_end"]
    
    # Verify both were written
    read_config = config_manager.load_config()
    assert len(read_config["journals"]) == 2
