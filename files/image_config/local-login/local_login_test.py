import local_login
import json
from unittest.mock import patch, call


def test_apply_sonic_config_to_linux():

    # -------------------------- Create fake input data ------------------------- #
    ssh_keys = json.loads(
        """\
    {
        "admin|key1": {
            "ssh-public-key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICy3VyLm2fshJow+5oGuKZvKpU7lmRdfGcW+nD5y3Z45 admin@host"
        },
        "admin|key2": {
            "ssh-public-key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA45654645wljdhahdakjhd9a8s79d807ajashdjasdads admin@vm"
        },
        "alice|key2": {
            "ssh-public-key": "ssh-ed25519 AAAAC3Nzasdasdsadasdsadsadaouoisadsadsadsaasdasdsadasdafwtty+nD5ytru545 alison@home"
        },
        "bob|key1": {
            "ssh-public-key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICy3Vasdsadasdai6hkjb0IasdsaadIIIASDasdasdaJJAa bob@devbox"
        },
        "tim|key1": {
            "ssh-public-key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICy3Vasdsadasdai6hkjb0IaasdasdaIIASDasdasdaJJAa tim@devbox"
        }
    }"""
    )

    local_login_users = json.loads(
        """\
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
    )
    linux_users = ["admin", "larry", "tim", "tacas_user"]

    # ------------------------------- Mock OS calls ------------------------------ #
    with patch("local_login.subprocess.run") as mock_run, patch(
        "local_login.is_remote_user"
    ) as mock_is_remote_user:

        # ----------------------- Mock is_remote_user function ----------------------- #
        mock_is_remote_user.side_effect = lambda username: username in ["tacas_user"]

        # ----------------------------- Invoke local login  ---------------------------- #
        local_login.apply_sonic_config_to_linux(
            ssh_keys, local_login_users, linux_users
        )

        expected_calls = [
            call(
                ["sudo", "usermod", "-aG", "sudo,redis,docker", "admin"],
                text=True,
                capture_output=True,
            ),
            call(
                ["sudo", "chpasswd", "-e"],
                text=True,
                input="admin:$6$PR8ha03JMI.StT.W$ofKf0uYDCocHXlLQ.tUcuN1U9gci.Mi/nQQWomujrcN9JSkuo6j1kNh.jDL.Y00h1jkfTk8T7EJ974SbjvR.R1",
                capture_output=False,
            ),
            call(
                ["sudo", "useradd", "--create-home", "--shell", "/bin/bash", "bob"],
                text=True,
                capture_output=True,
            ),
            call(
                ["sudo", "usermod", "-aG", "sudo,redis,docker", "bob"],
                text=True,
                capture_output=True,
            ),
            call(
                ["sudo", "chpasswd", "-e"],
                text=True,
                input="bob:$6$LFnHpZ7hp5SfYNAV$TakLFissCh97ZJtgbp9xHm/HnQn63Xpoe26HtcoK10xk9qVNH2XWp3Sy4YOQhLH0lVYyGIKQxAAsEBxgaTtux0",
                capture_output=False,
            ),
            call(["sudo", "passwd", "-d", "larry"], check=True),
            call(["sudo", "userdel", "--force", "larry"], check=True),
            call(["sudo", "rm", "-rf", "/home/larry"], check=True),
            call(["sudo", "passwd", "-d", "tim"], check=True),
        ]
        print(mock_run.mock_calls)
        mock_run.assert_has_calls(expected_calls, any_order=False)
        assert mock_run.call_count == len(expected_calls)
