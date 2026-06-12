path = 'app/src/main/java/com/psikochat/app/ui/auth/RegistrationScreen.kt'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = 'navController.navigate("login") { popUpTo("register") { inclusive = true } }'
new = 'navController.navigate("main_graph") {\r\n                popUpTo("auth_graph") { inclusive = true }\r\n                launchSingleTop = true\r\n            }'

if old not in content:
    print('ERROR: Target string not found!')
    print('Snippet around line 54:')
    lines = content.splitlines()
    for i, line in enumerate(lines[50:60], start=51):
        print(f'{i}: {repr(line)}')
else:
    content2 = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content2)
    print('OK: Navigation updated successfully.')
