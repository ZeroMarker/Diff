import flet as ft

def main(page: ft.Page):
    page.title = "Flet 示例"
    page.theme_mode = ft.ThemeMode.DARK

    page.add(
        ft.Text("欢迎使用 Flet!", size=30),
        ft.ElevatedButton("点我变色", on_click=lambda _: page.theme_mode == ft.ThemeMode.LIGHT),
    )

ft.app(target=main)
# 打包：flet pack main.py