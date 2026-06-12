path = 'app/src/main/java/com/psikochat/app/ui/auth/RegistrationScreen.kt'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# \r\r\n -> \r\n fix
content_fixed = content.replace('\r\r\n', '\r\n')

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content_fixed)
print('OK: Line endings fixed.')

# Verify the navigation block
if 'main_graph' in content_fixed:
    print('OK: main_graph navigation found.')
else:
    print('ERROR: main_graph navigation not found!')
