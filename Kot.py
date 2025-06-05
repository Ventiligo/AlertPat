import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("silaedr.codingprojects.ru", username="kot", password="dlONGEhmaNDstInOrNEs")

stdin, stdout, stderr = ssh.exec_command("ls")
print(stdout.read().decode())

ssh.close()