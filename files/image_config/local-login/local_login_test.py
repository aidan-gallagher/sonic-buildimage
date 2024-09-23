import local_login
import json


def test_apply_db_state_to_linux():

    # Mock subprocess run.
    commands = []

    def run_mock(command, **kwargs):
        commands.append(command)

    local_login.subprocess.run = run_mock

    # Fake data which `get_users_from_db()` would retrieve using `sonic-cfggen -d --var-json 'LOCAL_LOGIN'`.
    result = """\
    {
        "admin": {
            "password": "$6$PR8ha03JMI.StT.W$ofKf0uYDCocHXlLQ.tUcuN1U9gci.Mi/nQQWomujrcN9JSkuo6j1kNh.jDL.Y00h1jkfTk8T7EJ974SbjvR.R1"
        },
        "bob": {
            "password": "$6$LFnHpZ7hp5SfYNAV$TakLFissCh97ZJtgbp9xHm/HnQn63Xpoe26HtcoK10xk9qVNH2XWp3Sy4YOQhLH0lVYyGIKQxAAsEBxgaTtux0"
        },
        "invalid_user_without_password": {
        }
    }"""
    db_users = json.loads(result)

    # Fake data which `get_users_from_linux` would retrieve using `pwd.getpwall`
    linux_users = ["admin", "larry"]

    # Apply local_login logic with fake data.
    local_login.apply_db_state_to_linux(db_users, linux_users)

    # Assert the correct mocked subprocess run commands were invoked.

    # Assert admin user is sudo and password is set.
    assert commands[0] == ["sudo", "usermod", "-aG", "sudo", "admin"]
    assert commands[1] == ["sudo", "chpasswd", "-e"]

    # Assert bob is created, is sudo and password is set.
    assert commands[2] == [
        "sudo",
        "useradd",
        "--create-home",
        "--shell",
        "/bin/bash",
        "bob",
    ]
    assert commands[3] == ["sudo", "usermod", "-aG", "sudo", "bob"]
    assert commands[4] == ["sudo", "chpasswd", "-e"]

    # Assert larry is deleted and home directory removed.
    assert commands[5] == ["sudo", "userdel", "--force", "larry"]
    assert commands[6] == ["sudo", "rm", "-rf", "/home/larry"]


def test_no_db_state():

    # Mock subprocess run.
    commands = []

    def run_mock(command, **kwargs):
        commands.append(command)

    local_login.subprocess.run = run_mock

    # Fake data which `get_users_from_db()` would retrieve using `sonic-cfggen -d --var-json 'LOCAL_LOGIN'`.
    result = ""
    db_users = json.loads(result) if result else {}

    # Fake data which `get_users_from_linux` would retrieve using `pwd.getpwall`
    linux_users = ["admin", "larry"]

    # Apply local_login logic with fake data.
    local_login.apply_db_state_to_linux(db_users, linux_users)

    assert len(commands) == 0
