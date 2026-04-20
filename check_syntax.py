import ast

try:
    with open('tui.py', 'r') as f:
        content = f.read()
    
    # Parse the file
    ast.parse(content)
    print("No syntax errors found")
    
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.text}")
    print(f"Error: {e.msg}")
except Exception as e:
    print(f"Error: {e}")