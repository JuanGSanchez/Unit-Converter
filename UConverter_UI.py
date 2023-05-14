"""
Juan García Sánchez, 2023
"""

###############################################################################
#                                                                             #
# Magnitudes' unit converter: U Converter                                     #
# UI                                                                          #
#                                                                             #
###############################################################################

from tkinter import *
from tkinter import ttk, font, messagebox, filedialog, PhotoImage
from PIL import ImageTk, Image
import os
import gc



# ================= Program parameters ==========

__author__ = 'Juan García Sánchez'
__title__= 'U Converter'
__rootf__ = os.getcwd()
__version__ = '1.0'
__datver__ = '05-2023'
__pyver__ = '3.10.9'
__license__ = 'GPLv3'



# ================= UI class ====================

class UC_UI(Tk):

    def __init__(self):

# Main properties of the UI
        Tk.__init__(self)
        self.title(__title__)
        self.geometry('235x360+800+350')
        self.resizable(False, False)
        self.lift()
        self.focus_force()
        icon = PhotoImage(file =  __rootf__ + "/Logo UC.png")
        self.iconphoto(False, icon)
        self.config(bg = "#bfbfbf")

# Style settings
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family = 'TimesNewRoman', size = 12)
        self.option_add("*Font", default_font)  # Default font      

        self.style_opts = {'bg' : '#bfbfbf', 'fg' : 'black', 'font' : 'Verdana 12', 'activebackground' : '#bfbfbf', 'activeforeground' : 'green'}
        self.font_title = {'bg' : '#999999', 'fg' : 'blue', 'font' : 'Arial 12 bold'}
        self.font_entry = {'bg' : 'white', 'fg' : 'black', 'font' : 'Verdana 11'}
        self.font_text = {'bg' : 'darkblue', 'font' : "Arial 11", 'fg' : 'white'}

# UI variables
        self.dict_mag = {'*Select magnitude*' : -1, 'Mass' : 0, 'Length' : 1, 'Area' : 2, 'Volume' : 3, 'Time' : 4, 'Force' : 5, 'Energy' : 6, 'Pressure' : 7}
        self.dict_oders = {'' : 1, 'k' : 1E3, 'M' : 1E6, 'G' : 1E9, 'T' : 1E12}
        self.dict_units = []   # List of dictionaries with set of units, each one corresponds to a given magnitude

# UI layout
        '''Source path selection, from which all nested files or folders will be listed'''
        lab_path = Label(self, text = "Root path", justify = CENTER, bd = 2, width = 18, **self.font_title)
        lab_path.grid(row = 0, column = 0, padx = 10, pady = 7, ipadx = 10, ipady = 5)

# UI mainloop
        self.mainloop()



# ================= UI execution ================

if __name__ == '__main__':
    UC_UI()