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
import numpy as np
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
        width = 235
        height = 385
        x_pos = (self.winfo_screenwidth() - width - self.winfo_rootx() + self.winfo_x())//2
        y_pos = (self.winfo_screenheight() - height - self.winfo_rooty() + self.winfo_y())//2
        self.geometry('{}x{}+{}+{}'.format(width, height, x_pos, y_pos))
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

        self.font_title = {'bg' : '#999999', 'fg' : 'blue', 'font' : 'Arial 12 bold'}
        self.font_entry = {'bg' : 'white', 'fg' : 'black', 'font' : 'Verdana 11'}
        self.font_val = {'bg' : '#bfbfbf', 'fg' : 'black', 'font' : 'Verdana 11'}
        self.font_text = {'bg' : '#bfbfbf', 'fg' : 'black', 'font' : 'Verdana 12'}
        self.font_man = {'bg' : 'darkblue', 'font' : "Arial 11", 'fg' : 'white'}

# UI variables
        ''' Dictionary of the magnitudes in the program '''
        self.magnitudes_names = {'*Select magnitude*' : -1}
        ''' Dictionary of the orders of magnitude available, in decimal '''
        self.dict_order1 = {'q' : -30, 'r' : -27, 'y' : -24, 'z' : -21, 'a' : -18, 'f' : -15, 'p' : -12,
                            'n' : -9, '\u03bc' : -6, 'm' : -3, '1' : 0, 'k' : 3, 'M' : 6, 'G' : 9, 'T' : 12,
                            'P' : 15, 'E' : 18, 'Z' : 21, 'Y' : 24, 'R' : 27, 'Q' : 30}
        ''' Dictionary of the magnitudes in the program, for data magnitude '''
        self.dict_order2 = {'1' : 0, 'k' : 1, 'M' : 2, 'G' : 3, 'T' : 4, 'P' : 5, 'E' : 6, 'Z' : 7, 'Y' : 8, 'R' : 9, 'Q' : 10}

        ''' List of magnitudes with their units and conversions associated, from database file "Magnitudes.txt".
         Instruction must be followed for a correct management and update of this file: for each magnitude,
            First line, magnitude's name
            Second line, names of the units, comma separated
            Third line, conversion factors associated to previous units, in the same order
         Magnitudes can be rearranged in any order inside the file, but always following this structure.
         Avoid empty end line.'''
        with open(__rootf__ + "/Magnitudes.txt", 'r') as fl:
            body = fl.read().splitlines()
            if len(body)%3 != 0:
                print('Bad magnitude database structure, leaving UConverter...')
                self.exit()
            self.magnitudes = []
            for i in range(len(body)//3):
                self.magnitudes.append({})
                self.magnitudes_names[body[i*3]] = i
                for var1, var2 in zip(body[i*3 + 1].split(','), body[i*3 + 2].split(',')):
                    if '2' in var1:
                        var1 = var1.replace('2', '\u00B2')
                    elif '3' in var1:
                        var1 = var1.replace('3', '\u00B3')
                    self.magnitudes[-1][str(var1)] = float(var2)
        self.magnitudes.append({'' : 0, ' ' : 1})

        ''' Values and control derivatives '''
        self.val1 = DoubleVar(value = 0)
        self.val2 = DoubleVar(value = 0)
        self.val1_old = DoubleVar(value = 0)
        self.val2_old = DoubleVar(value = 0)

# UI layout
        '''Magnitude selection, among the ones that have been added to the application'''
        lab_mag = Label(self, text = "Magnitude", justify = CENTER, bd = 2, width = 18, **self.font_title)
        lab_mag.grid(row = 0, column = 0, padx = 10, pady = 7, ipadx = 10, ipady = 5)
        self.Cb_opt1 = ttk.Combobox(self, values = list(self.magnitudes_names.keys()), background = "#e6e6e6", state = "readonly", width = 18)
        self.Cb_opt1.set(list(self.magnitudes_names.keys())[0])
        self.Cb_opt1.grid(row = 1, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5)
        self.Cb_opt1.bind("<<ComboboxSelected>>", self.mag_selection)

        '''First unit selection, including order of magnitude and actual value in scientific notation'''
        lab_unit1 = Label(self, text = "From:", anchor = W, bd = 2, width = 10, **self.font_text)
        lab_unit1.grid(row = 2, column = 0, padx = 10, pady = 7, ipadx = 10, ipady = 5, sticky = W)
        self.lab_val1 = Label(self, text = "{:.1e}".format(self.val1.get()), justify = CENTER, bd = 2, width = 7, **self.font_val)
        self.lab_val1.grid(row = 2, column = 0, padx = 10, pady = 7, ipadx = 1, ipady = 5, sticky = E)
        self.Lb_order1 = Label(self, text = "1", relief = RIDGE, width = 2)
        self.Lb_order1.grid(row = 3, column = 0, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_order1.bind("<MouseWheel>", lambda event: self.change_units(event, self.Lb_order1))
        self.Lb_order1.bind('<1>', lambda event: self.reset_order(self.Lb_order1))
        self.Cb_opt2 = ttk.Combobox(self, background = "#e6e6e6", state = DISABLED, width = 14)
        self.Cb_opt2.grid(row = 3, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5, sticky = E)
        self.Cb_opt2.bind("<<ComboboxSelected>>", lambda event: self.unit_converter(1))
        self.ent_unit1 = Entry(self, name = 'unit1', textvariable = self.val1, justify = LEFT, bd = 5, relief = SUNKEN, state = DISABLED, width = 13, **self.font_entry)
        self.ent_unit1.grid(row = 4, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5, sticky = W)
        self.ent_unit1.bind("<MouseWheel>", lambda event: self.ent_unit1.xview_scroll(int(event.delta/40), 'units'))
        self.Lb_sweep1 = Label(self, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_sweep1.grid(row = 4, column = 0, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = E)
        self.Lb_sweep1.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_sweep1))
        self.Lb_sweep1.bind('<1>', lambda event: self.Lb_sweep1.config(text = '...'))

        '''Second unit selection, including order of magnitude and actual value in scientific notation'''
        lab_unit2 = Label(self, text = "To:", anchor = W, bd = 2, width = 10, **self.font_text)
        lab_unit2.grid(row = 5, column = 0, padx = 10, pady = 7, ipadx = 10, ipady = 5, sticky = W)
        self.lab_val2 = Label(self, text = "{:.1e}".format(self.val2.get()), justify = CENTER, bd = 2, width = 7, **self.font_val)
        self.lab_val2.grid(row = 5, column = 0, padx = 10, pady = 7, ipadx = 1, ipady = 5, sticky = E)
        self.Lb_order2 = Label(self, text = "1", relief = RIDGE, width = 2)
        self.Lb_order2.grid(row = 6, column = 0, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_order2.bind("<MouseWheel>", lambda event: self.change_units(event, self.Lb_order2))
        self.Lb_order2.bind('<1>', lambda event: self.reset_order(self.Lb_order2))
        self.Cb_opt3 = ttk.Combobox(self, background = "#e6e6e6", state = DISABLED, width = 14)
        self.Cb_opt3.grid(row = 6, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5, sticky = E)
        self.Cb_opt3.bind("<<ComboboxSelected>>", lambda event: self.unit_converter(1))
        self.ent_unit2 = Entry(self, name = 'unit2', textvariable = self.val2, justify = LEFT, bd = 5, relief = SUNKEN, state = DISABLED,  width = 13, **self.font_entry)
        self.ent_unit2.grid(row = 7, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5, sticky = W)
        self.ent_unit2.bind("<MouseWheel>", lambda event: self.ent_unit2.xview_scroll(int(event.delta/40), 'units'))
        self.Lb_sweep2 = Label(self, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_sweep2.grid(row = 7, column = 0, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = E)
        self.Lb_sweep2.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_sweep2))
        self.Lb_sweep2.bind('<1>', lambda event: self.Lb_sweep2.config(text = '...'))

# UI manual
        text_man1 = 'List of magnitudes added to the application.'
        text_man2 = 'Write or press Enter\nto run the conversion.'
        text_man3 = 'Scroll to change order of magnitude.\nClick to reset.'
        text_man4 = 'Scroll to change digit position sweep.\nClick to reset.'
        text_man5 = 'Actual total value in scientific notation.'
        fr_man = Toplevel(self, bd= 2, bg = 'darkblue')
        fr_man.resizable(False, False)
        fr_man.overrideredirect(True)
        fr_man.wm_attributes('-alpha', 0.8)
        fr_man.withdraw()
        self.fr_lab = Label(fr_man, justify = LEFT, bd = 2, **self.font_man)
        self.fr_lab.grid(padx = 1, pady = 1, sticky = W)
        self.Cb_opt1.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [204, 33, 290, 30], text_man1))
        self.ent_unit1.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [161, 39, 150, 45], text_man2))
        self.ent_unit2.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [161, 39, 150, 45], text_man2))
        self.Lb_order1.bind("<Motion>", lambda event: self.show_manual(event, fr_man, [33, 33, 248, 45], text_man3))
        self.Lb_order2.bind("<Motion>", lambda event: self.show_manual(event, fr_man, [33, 33, 248, 45], text_man3))
        self.Lb_sweep1.bind("<Motion>", lambda event: self.show_manual(event, fr_man, [33, 33, 253, 45], text_man4))
        self.Lb_sweep2.bind("<Motion>", lambda event: self.show_manual(event, fr_man, [33, 33, 253, 45], text_man4))
        self.lab_val1.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [70, 33, 255, 30], text_man5))
        self.lab_val2.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [70, 33, 255, 30], text_man5))

# UI contextual menu
        self.menucontext = Menu(self, tearoff = 0)
        self.menucontext.add_command(label = "About...", command = lambda : print('Author: '
                                    + __author__ + '\nVersion: ' + __version__ + '\nLicense: ' + __license__))
        self.menucontext.add_command(label = "Exit", command = self.exit)

# UI bindings
        self.ent_unit1.bind("<KeyRelease>", lambda event: self.unit_converter(1))
        self.ent_unit2.bind("<KeyRelease>", lambda event: self.unit_converter(2))
        self.ent_unit1.bind("<Up>", lambda event: self.change_values(event, 1, self.ent_unit1, 1))
        self.ent_unit1.bind("<Down>", lambda event: self.change_values(event, -1, self.ent_unit1, 1))
        self.ent_unit1.bind("<MouseWheel>", lambda event: self.change_values(event, int(event.delta/120), self.ent_unit1, 1))
        self.ent_unit2.bind("<Up>", lambda event: self.change_values(event, 1, self.ent_unit2, 2))
        self.ent_unit2.bind("<Down>", lambda event: self.change_values(event, -1, self.ent_unit2, 2))
        self.ent_unit2.bind("<MouseWheel>", lambda event: self.change_values(event, int(event.delta/120), self.ent_unit2, 2))
        self.bind("<3>", self.show_menucontext)
        self.bind("<Return>", lambda event: self.unit_converter())
        self.bind("<Control_R>", lambda event: self.exit())

# UI mainloop
        self.mainloop()


# Additional functions of the class
    ''' Magnitude selection '''
    def mag_selection(self, event):
        if self.Cb_opt1.get() == '*Select magnitude*':
            self.Cb_opt2.config(state = DISABLED)
            self.Cb_opt2.set('')
            self.ent_unit1.config(state = DISABLED)
            self.val1.set(0.0)
            self.val1_old.set(0.0)
            self.lab_val1.config(text = "{:.1e}".format(self.val1.get()))
            self.Cb_opt3.config(state = DISABLED)
            self.Cb_opt3.set('')
            self.ent_unit2.config(state = DISABLED)
            self.val2.set(0.0)
            self.val2_old.set(0.0)
            self.lab_val2.config(text = "{:.1e}".format(self.val2.get()))
        else:
            self.Cb_opt2.config(values = list(self.magnitudes[self.magnitudes_names[self.Cb_opt1.get()]].keys()), state = "readonly")
            self.Cb_opt2.set(list(self.magnitudes[self.magnitudes_names[self.Cb_opt1.get()]].keys())[0])
            self.ent_unit1.config(state = NORMAL)
            self.Cb_opt3.config(values = list(self.magnitudes[self.magnitudes_names[self.Cb_opt1.get()]].keys()), state = "readonly")
            self.Cb_opt3.set(list(self.magnitudes[self.magnitudes_names[self.Cb_opt1.get()]].keys())[1])
            self.ent_unit2.config(state = NORMAL)

            if self.Cb_opt1.get() == 'Data':
                self.list_order1 = list(self.dict_order2.values())
                self.list_order2 = list(self.dict_order2.keys())
            else:
                self.list_order1 = list(self.dict_order1.values())
                self.list_order2 = list(self.dict_order1.keys())

            self.unit_converter(1)


    ''' Change order of magnitude '''
    def change_units(self, e, lab):
        order_source = self.dict_order2 if self.Cb_opt1.get() == 'Data' else self.dict_order1

        if self.Cb_opt1.get() != '*Select magnitude*':
            idn = int(self.list_order1.index(order_source[lab["text"]]) + e.delta/120)
            if 0 <= idn < len(self.list_order1):
                lab.config(text = self.list_order2[idn])

            self.unit_converter(1)


    ''' Change input values with up and down keys '''
    def change_values(self, event, e, lab, opt):
        if self.Cb_opt1.get() != '*Select magnitude*':
            self.check_value(self.val1)
            self.check_value(self.val2)

            if str(event.widget)[-1] == '1':
                decimals = len(str(self.val1.get()).split('.')[-1]) if self.Lb_sweep1['text'] == '...' else -int(self.Lb_sweep1['text'])
                self.val1.set(np.round(self.val1.get() + e*10**(-decimals), decimals))
            else:
                decimals = len(str(self.val2.get()).split('.')[-1]) if self.Lb_sweep2['text'] == '...' else -int(self.Lb_sweep2['text'])
                self.val2.set(np.round(self.val2.get() + e*10**(-decimals), decimals))

            self.unit_converter(opt)


    ''' Change decimal position to sweep with up and down keys '''
    def change_sweep(self, e, lab):
        init = lab["text"]
        match init:
            case '...':
                init = str(int(e.delta/120)) if e.delta < 0 else '0'
            case '0':
                init = '...' if e.delta < 0 else '1'
            case '-1':
                init = '-2' if e.delta < 0 else '...'
            case '99':
                init = str(int(init) + int(e.delta/120)) if e.delta < 0 else '99'
            case '-99':
                init = '-99' if e.delta < 0 else str(int(init) + int(e.delta/120))
            case _:
                init = str(int(init) + int(e.delta/120))
        lab.config(text = init)


    ''' Function to reset the order of magnitude and update the result '''
    def reset_order(self, lab):
        lab.config(text = '1')

        if self.Cb_opt1.get() != '*Select magnitude*':
            self.unit_converter(1)


    ''' Check if there is a number in the tkinter variable '''
    def check_value(self, val):
        try:
            val.get()
        except:
            val.set(0)


    ''' Unit converter main function '''
    def unit_converter(self, e = 0):
        if self.Cb_opt1.get() != '*Select magnitude*':
            if self.Cb_opt1.get() == 'Data':
                order_source = self.dict_order2
                base = 1024
            else:
                order_source = self.dict_order1
                base = 10

            self.check_value(self.val1)
            self.check_value(self.val2)

            if self.val1.get() != self.val1_old.get() or e == 1:
                if self.val1.get() < 0:
                    self.val1.set(0)
                self.val1_old.set(self.val1.get())
                order1 = base**order_source[self.Lb_order1["text"]]
                order2 = base**order_source[self.Lb_order2["text"]]
                conversion1 = self.magnitudes[self.magnitudes_names[self.Cb_opt1.get()]][self.Cb_opt2.get()]
                conversion2 = self.magnitudes[self.magnitudes_names[self.Cb_opt1.get()]][self.Cb_opt3.get()]
                self.lab_val1.config(text = "{:.1e}".format(self.val1.get()*order1))
                self.val2.set((self.val1.get()*order1*conversion1)/(order2*conversion2))
                self.val2_old.set(self.val2.get())
                self.lab_val2.config(text = "{:.1e}".format(self.val2.get()))
            elif self.val2.get() != self.val2_old.get() or e == 2:
                if self.val2.get() < 0:
                    self.val2.set(0)
                self.val2_old.set(self.val2.get())
                order1 = base**order_source[self.Lb_order1["text"]]
                order2 = base**order_source[self.Lb_order2["text"]]
                conversion1 = self.magnitudes[self.magnitudes_names[self.Cb_opt1.get()]][self.Cb_opt2.get()]
                conversion2 = self.magnitudes[self.magnitudes_names[self.Cb_opt1.get()]][self.Cb_opt3.get()]
                self.lab_val2.config(text = "{:.1e}".format(self.val2.get()*order2))
                self.val1.set((self.val2.get()*order2*conversion2)/(order1*conversion1))
                self.val1_old.set(self.val1.get())
                self.lab_val1.config(text = "{:.1e}".format(self.val1.get()))


    ''' Show manual widget '''
    def show_manual(self, e, fr, pos, text_man):
        if 0 < e.x < pos[0] and 0 < e.y < pos[1]:
            fr.deiconify()
            self.fr_lab.config(text = text_man)
            fr.geometry('{}x{}+{}+{}'.format(pos[2], pos[3], e.x_root + 20, e.y_root + 20))
        else:
            fr.withdraw()


    ''' Show contextual menu '''
    def show_menucontext(self, e):
        self.menucontext.post(e.x_root, e.y_root)


    ''' Exit function '''
    def exit(self):
        print('Exiting Unit Converter...')
        self.quit()
        self.destroy()
        for name in dir():
            if not name.startswith('_'):
                del locals()[name]
        gc.collect()
        del self



# ================= UI execution ================

if __name__ == '__main__':
    UC_UI()