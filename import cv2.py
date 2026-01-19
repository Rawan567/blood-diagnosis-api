import cv2
import numpy as np
from tkinter import *
from tkinter import filedialog, simpledialog, messagebox
from PIL import Image, ImageTk

# ================= GLOBAL =================
current = None
original_image = None
history = []

# ================= TOOLTIP =================
class ToolTip:
    def __init__(self, widget, text):
        self.tip = None
        widget.bind("<Enter>", lambda e: self.show(widget, text))
        widget.bind("<Leave>", lambda e: self.hide())

    def show(self, widget, text):
        if self.tip: return
        x, y = widget.winfo_rootx()+20, widget.winfo_rooty()+20
        self.tip = Toplevel(widget)
        self.tip.overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")
        Label(self.tip, text=text, bg="#ffffe0",
              relief=SOLID, borderwidth=1).pack()

    def hide(self):
        if self.tip:
            self.tip.destroy()
            self.tip = None

# ================= DISPLAY =================
def show_image(img):
    global current
    current = img
    if len(img.shape) == 3:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
    img_display.config(image=imgtk)
    img_display.image = imgtk

# ================= HISTORY =================
def save_state():
    if current is not None:
        history.append(current.copy())
        if len(history) > 20:
            history.pop(0)

def undo():
    if not history:
        messagebox.showwarning("Undo", "No history available")
        return
    show_image(history.pop())

# ================= LOAD / SAVE =================
def load_image():
    global original_image
    path = filedialog.askopenfilename()
    if path:
        img = cv2.imread(path)
        original_image = img.copy()
        history.clear()
        show_image(img)

def save_image():
    if current is None: return
    path = filedialog.asksaveasfilename(defaultextension=".png")
    if path:
        cv2.imwrite(path, current)

def reset_image():
    if original_image is not None:
        save_state()
        show_image(original_image.copy())

# ================= INFO =================
def show_info():
    if current is None: return
    h, w = current.shape[:2]
    ch = 1 if len(current.shape) == 2 else 3
    messagebox.showinfo("Image Info",
                        f"Width: {w}\nHeight: {h}\nChannels: {ch}")

def show_pixel():
    if current is None: return
    x = simpledialog.askinteger("X","X:",0,current.shape[1]-1)
    y = simpledialog.askinteger("Y","Y:",0,current.shape[0]-1)
    if x is not None and y is not None:
        messagebox.showinfo("Pixel Value", f"{current[y,x]}")

# ================= TRANSFORMS =================
def flip_x(): save_state(); show_image(cv2.flip(current,1))
def flip_y(): save_state(); show_image(cv2.flip(current,0))
def flip_xy(): save_state(); show_image(cv2.flip(current,-1))

def rotate():
    if current is None: return
    angle = simpledialog.askfloat("Rotate","Angle:")
    if angle is None: return
    save_state()
    h,w = current.shape[:2]
    M = cv2.getRotationMatrix2D((w//2,h//2), angle, 1)
    show_image(cv2.warpAffine(current, M, (w,h)))

def translate():
    if current is None: return
    x = simpledialog.askinteger("Translate","X shift:")
    y = simpledialog.askinteger("Translate","Y shift:")
    if x is None or y is None: return
    save_state()
    M = np.float32([[1,0,x],[0,1,y]])
    show_image(cv2.warpAffine(current, M,
              (current.shape[1], current.shape[0])))

def zoom():
    if current is None: return
    factor = simpledialog.askfloat("Zoom","Factor (>1):")
    if factor is None or factor <= 1: return
    save_state()
    h,w = current.shape[:2]
    nh,nw = int(h/factor), int(w/factor)
    y1,x1 = (h-nh)//2,(w-nw)//2
    crop = current[y1:y1+nh, x1:x1+nw]
    show_image(cv2.resize(crop,(w,h)))

# ================= FILTERS =================
def gaussian_filter():
    if current is None: return
    save_state()
    k = simpledialog.askinteger("Gaussian","Kernel size (odd):",3,15)
    if k is None or k%2==0: return
    show_image(cv2.GaussianBlur(current,(k,k),0))

def sobel_filter():
    if current is None: return
    save_state()
    gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    sx = cv2.Sobel(gray, cv2.CV_64F,1,0)
    sy = cv2.Sobel(gray, cv2.CV_64F,0,1)
    mag = cv2.magnitude(sx,sy)
    show_image(cv2.convertScaleAbs(mag))

def laplacian_filter():
    if current is None: return
    save_state()
    gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    show_image(cv2.convertScaleAbs(lap))

# ================= SEGMENTATION =================
def region_growing():
    if current is None: return
    save_state()
    gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)

    x = simpledialog.askinteger("Seed X","X:")
    y = simpledialog.askinteger("Seed Y","Y:")
    t = simpledialog.askinteger("Threshold","Threshold:",5,50)
    if None in (x,y,t): return

    h,w = gray.shape
    seed = gray[y,x]
    mask = np.zeros((h,w),np.uint8)

    for i in range(h):
        for j in range(w):
            if abs(int(gray[i,j]) - int(seed)) < t:
                mask[i,j] = 255
    show_image(mask)

# ================= GUI =================
root = Tk()
root.title("Complete Image Processing Toolbox")
root.geometry("1400x800")

left = Frame(root,bg="#222",width=220)
left.pack(side=LEFT,fill=Y)

right = Frame(root,bg="#222",width=220)
right.pack(side=RIGHT,fill=Y)

img_display = Label(root,bg="black")
img_display.pack(expand=True,fill=BOTH)

def add_btn(frame,text,cmd,tip):
    b = Button(frame,text=text,command=cmd,
               width=22,height=2,bg="#66ccff")
    b.pack(pady=2)
    ToolTip(b, tip)

# LEFT BUTTONS
left_buttons = [
    ("Load Image", load_image,"Load image"),
    ("Save Image", save_image,"Save image"),
    ("Reset Image", reset_image,"Reset"),
    ("Undo", undo,"Undo"),
    ("Image Info", show_info,"Info"),
    ("Pixel Value", show_pixel,"Pixel"),
    ("Flip X", flip_x,"Flip X"),
    ("Flip Y", flip_y,"Flip Y"),
    ("Flip XY", flip_xy,"Flip XY"),
    ("Rotate", rotate,"Rotate"),
    ("Translate", translate,"Translate"),
    ("Zoom", zoom,"Zoom"),
]

for b in left_buttons:
    add_btn(left,*b)

# RIGHT BUTTONS
right_buttons = [
    ("Gaussian Filter", gaussian_filter,"Gaussian"),
    ("Sobel Filter", sobel_filter,"Sobel"),
    ("Laplacian Filter", laplacian_filter,"Laplacian"),
    ("Region Growing", region_growing,"Segmentation"),
    ("Exit", root.quit,"Exit"),
]

for b in right_buttons:
    add_btn(right,*b)

root.mainloop()
