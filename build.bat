@echo off
chcp 65001 >nul
REM 在 Windows 上打包成單一 EXE：dist\LeetCodeDungeon.exe
python -m pip install -r requirements.txt pyinstaller || goto :err
python -m PyInstaller --noconfirm --onefile --name LeetCodeDungeon ^
  --icon assets\icon.ico ^
  --add-data "game\static;game\static" ^
  --add-data "data\problems.json;data" ^
  --collect-submodules game ^
  --exclude-module xhtml2pdf --exclude-module reportlab ^
  launcher.py || goto :err
echo.
echo 完成！EXE 在 dist\LeetCodeDungeon.exe
goto :eof
:err
echo 打包失敗，請看上面的錯誤訊息。
exit /b 1
