@echo off
mkdir static 2>nul
mkdir static\css 2>nul
mkdir static\js 2>nul
mkdir templates 2>nul
mkdir downloads 2>nul

if exist index.html (
    move /Y index.html templates\index.html
)

echo Directory structure created successfully!
