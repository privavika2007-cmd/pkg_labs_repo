import sys
import tkinter as tk

from ui import App


def main():
    sys.setswitchinterval(0.001)
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
