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
        self.geometry('235x385+800+350')
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
        self.dict_mag = {'*Select magnitude*' : -1, 'Mass' : 0, 'Length' : 1, 'Area' : 2, 'Volume' : 3, 'Time' : 4, 'Energy' : 5, 'Pressure' : 6, 'Data' : 7}
        self.dict_order1 = {'q' : -30, 'r' : -27, 'y' : -24, 'z' : -21, 'a' : -18, 'f' : -15, 'p' : -12,
                            'n' : -9, '\u03bc' : -6, 'm' : -3, '1' : 0, 'k' : 3, 'M' : 6, 'G' : 9, 'T' : 12,
                            'P' : 15, 'E' : 18, 'Z' : 21, 'Y' : 24, 'R' : 27, 'Q' : 30}
        self.dict_order2 = {'1' : 0, 'k' : 1, 'M' : 2, 'G' : 3, 'T' : 4, 'P' : 5, 'E' : 6, 'Z' : 7, 'Y' : 8, 'R' : 9, 'Q' : 10}
        self.list_order1 = list(self.dict_order1.values())
        self.list_order2 = list(self.dict_order1.keys())
        dict_mass = {'gram (g)' : 1.0, 'Av. pound (lb)' : 453.6, 'Av. ounce (oz)' : 28.35}
        dict_length = {'meter (m)' : 1.0, 'inch (in)' : 0.0254, 'yard (yd)' : 0.9144, 'mile (mi)' : 1609.34}
        dict_area = {'square meter (m\u00B2)' : 1.0, 'square inch (in\u00B2)' : 0.00064516, 'square yard (yd\u00B2)' : 0.836127, 'square mile (mi\u00B2)' : 2.59E6}
        dict_volume = {'cubic meter (m\u00B3)' : 1.0, 'litre (l)' : 0.001, 'Imp. pint (pt)' : 0.000568261, 'US pint (pt)' : 0.000473176}
        dict_time = {'second (s)' : 1.0, 'minute (min)' : 60, 'hour (hr)' : 3600, 'day (d)' : 86400}
        dict_energy = {'jule (J)' : 1.0, 'calorie (cal)' : 4.184, 'electronvolt (Ev)' : 1.6022E-19, 'watt-hour (Wh)' : 3600}
        dict_pressure = {'Pascal (Pa)' : 1.0, 'bar (b)' : 100000, 'atmosphere (atm)' : 101325, 'mm Hg' : 133.322, 'Torr ()': 133.322}
        dict_data = {'bit (b)' : 1.0, 'byte (B)' : 8.0}
        self.dict_units = [dict_mass, dict_length, dict_area, dict_volume, dict_time, 
                           dict_energy, dict_pressure, dict_data, {'' : 0, ' ' : 1}]   # List of dictionaries with set of units, each one corresponds to a given magnitude
        self.val1 = DoubleVar(value = 0)
        self.val2 = DoubleVar(value = 0)
        self.val1_old = DoubleVar(value = 0)
        self.val2_old = DoubleVar(value = 0)

# UI layout
        '''Source path selection, from which all nested files or folders will be listed'''
        lab_mag = Label(self, text = "Magnitude", justify = CENTER, bd = 2, width = 18, **self.font_title)
        lab_mag.grid(row = 0, column = 0, padx = 10, pady = 7, ipadx = 10, ipady = 5)
        self.Cb_opt1 = ttk.Combobox(self, values = list(self.dict_mag.keys()), background = "#e6e6e6", state = "readonly", width = 18)
        self.Cb_opt1.set(list(self.dict_mag.keys())[0])
        self.Cb_opt1.grid(row = 1, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5)
        self.Cb_opt1.bind("<<ComboboxSelected>>", self.mag_selection)

        lab_unit1 = Label(self, text = "From:", anchor = W, bd = 2, width = 10, **self.font_text)
        lab_unit1.grid(row = 2, column = 0, padx = 10, pady = 7, ipadx = 10, ipady = 5, sticky = W)
        self.lab_val1 = Label(self, text = "{:.1e}".format(self.val1.get()), justify = CENTER, bd = 2, width = 7, **self.font_val)
        self.lab_val1.grid(row = 2, column = 0, padx = 10, pady = 7, ipadx = 1, ipady = 5, sticky = E)
        self.Lb_order1 = Label(self, text = "1", relief = RIDGE, width = 2)
        self.Lb_order1.grid(row = 3, column = 0, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_order1.bind("<MouseWheel>", lambda event: self.change_units(event, self.Lb_order1))
        self.Cb_opt2 = ttk.Combobox(self, values = list(self.dict_units[self.dict_mag[self.Cb_opt1.get()]].keys()), background = "#e6e6e6", state = "readonly", width = 14)
        self.Cb_opt2.set(list(self.dict_units[self.dict_mag[self.Cb_opt1.get()]].keys())[0])
        self.Cb_opt2.grid(row = 3, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5, sticky = E)
        self.Cb_opt2.bind("<<ComboboxSelected>>", lambda event: self.unit_converter(1))
        self.ent_unit1 = Entry(self, textvariable = self.val1, justify = LEFT, bd = 5, relief = SUNKEN, width = 18, **self.font_entry)
        self.ent_unit1.grid(row = 4, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5)
        self.ent_unit1.bind("<MouseWheel>", lambda event: self.ent_unit1.xview_scroll(int(event.delta/40), 'units'))

        lab_unit2 = Label(self, text = "To:", anchor = W, bd = 2, width = 10, **self.font_text)
        lab_unit2.grid(row = 5, column = 0, padx = 10, pady = 7, ipadx = 10, ipady = 5, sticky = W)
        self.lab_val2 = Label(self, text = "{:.1e}".format(self.val2.get()), justify = CENTER, bd = 2, width = 7, **self.font_val)
        self.lab_val2.grid(row = 5, column = 0, padx = 10, pady = 7, ipadx = 1, ipady = 5, sticky = E)
        self.Lb_order2 = Label(self, text = "1", relief = RIDGE, width = 2)
        self.Lb_order2.grid(row = 6, column = 0, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_order2.bind("<MouseWheel>", lambda event: self.change_units(event, self.Lb_order2))
        self.Cb_opt3 = ttk.Combobox(self, values = list(self.dict_units[self.dict_mag[self.Cb_opt1.get()]].keys()), background = "#e6e6e6", state = "readonly", width = 14)
        self.Cb_opt3.set(list(self.dict_units[self.dict_mag[self.Cb_opt1.get()]].keys())[1])
        self.Cb_opt3.grid(row = 6, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5, sticky = E)
        self.Cb_opt3.bind("<<ComboboxSelected>>", lambda event: self.unit_converter(1))
        self.ent_unit2 = Entry(self, textvariable = self.val2, justify = LEFT, bd = 5, relief = SUNKEN,  width = 18, **self.font_entry)
        self.ent_unit2.grid(row = 7, column = 0, padx = 10, pady = 5, ipadx = 10, ipady = 5)
        self.ent_unit2.bind("<MouseWheel>", lambda event: self.ent_unit2.xview_scroll(int(event.delta/40), 'units'))

# UI manual
        text_man1 = 'List of magnitudes added to the application.'
        text_man2 = 'Press Enter to run the conversion.'
        text_man3 = 'Scroll to change order of magnitude.'
        text_man4 = 'Actual total value in scientific notation.'
        fr_man = Toplevel(self, bd= 2, bg = 'darkblue')
        fr_man.resizable(False, False)
        fr_man.overrideredirect(True)
        fr_man.wm_attributes('-alpha', 0.8)
        fr_man.withdraw()
        self.fr_lab = Label(fr_man, justify = LEFT, bd = 2, **self.font_man)
        self.fr_lab.grid(padx = 1, pady = 1, sticky = W)
        self.Cb_opt1.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [203, 32, 290, 30], text_man1))
        self.ent_unit1.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [209, 38, 235, 30], text_man2))
        self.ent_unit2.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [209, 38, 235, 30], text_man2))
        self.Lb_order1.bind("<Motion>", lambda event: self.show_manual(event, fr_man, [30, 30, 248, 30], text_man3))
        self.Lb_order2.bind("<Motion>", lambda event: self.show_manual(event, fr_man, [30, 30, 248, 30], text_man3))
        self.lab_val1.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [70, 30, 255, 30], text_man4))
        self.lab_val2.bind("<Motion>", lambda event : self.show_manual(event, fr_man, [70, 30, 255, 30], text_man4))

# UI contextual menu
        self.menucontext = Menu(self, tearoff = 0)
        self.menucontext.add_command(label = "About...", command = lambda : print('Author: '
                                    + __author__ + '\nVersion: ' + __version__ + '\nLicense: ' + __license__))
        self.menucontext.add_command(label = "Exit", command = self.exit)

# UI bindings
        self.ent_unit1.bind("<KeyRelease>", lambda event: self.unit_converter(1))
        self.ent_unit2.bind("<KeyRelease>", lambda event: self.unit_converter(0))
        self.ent_unit1.bind("<Up>", lambda event: self.change_values(1))
        self.ent_unit1.bind("<Down>", lambda event: self.change_values(-1))
        self.ent_unit2.bind("<Up>", lambda event: self.change_values(1))
        self.ent_unit2.bind("<Down>", lambda event: self.change_values(-1))
        self.bind("<3>", self.show_menucontext)
        self.bind("<Return>", lambda event: self.unit_converter())
        self.bind("<Control_R>", lambda event: self.exit())

# UI mainloop
        self.mainloop()


# Additional functions of the class
    ''' Magnitude selection '''
    def mag_selection(self, event):
        self.Cb_opt2.config(values = list(self.dict_units[self.dict_mag[self.Cb_opt1.get()]].keys()))
        self.Cb_opt2.set(list(self.dict_units[self.dict_mag[self.Cb_opt1.get()]].keys())[0])
        self.Cb_opt3.config(values = list(self.dict_units[self.dict_mag[self.Cb_opt1.get()]].keys()))
        self.Cb_opt3.set(list(self.dict_units[self.dict_mag[self.Cb_opt1.get()]].keys())[1])

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
        try:
            idn = int(self.list_order1.index(order_source[lab["text"]]) + e.delta/120)
        except:
            idn = 0
        if 0 <= idn < len(self.list_order1):
            lab.config(text = self.list_order2[idn])

        self.unit_converter(1)


    def change_values(self, e):
        decimals = len(str(self.val1.get()).split('.')[-1])
        self.val1.set(np.round(self.val1.get() + e*10**(-decimals), decimals))

        self.unit_converter(1)


    ''' Unit converter main function '''
    def unit_converter(self, e = 0):
        if self.Cb_opt1.get() == 'Data':
            order_source = self.dict_order2
            base = 1024
        else:
            order_source = self.dict_order1
            base = 10
        try:
            if self.val1.get() != self.val1_old.get() or e == 1:
                self.val1_old.set(self.val1.get())
                if self.val1.get() >= 0:
                    order1 = base**order_source[self.Lb_order1["text"]]
                    order2 = base**order_source[self.Lb_order2["text"]]
                    conversion1 = self.dict_units[self.dict_mag[self.Cb_opt1.get()]][self.Cb_opt2.get()]
                    conversion2 = self.dict_units[self.dict_mag[self.Cb_opt1.get()]][self.Cb_opt3.get()]
                    self.lab_val1.config(text = "{:.1e}".format(self.val1.get()*order1))
                    self.val2.set((self.val1.get()*order1*conversion1)/(order2*conversion2))
                else:
                    self.val2.set(None)
                self.val2_old.set(self.val2.get())
                self.lab_val2.config(text = "{:.1e}".format(self.val2.get()))
            elif self.val2.get() != self.val2_old.get():
                self.val2_old.set(self.val2.get())
                if self.val2.get() >= 0:
                    order1 = base**order_source[self.Lb_order1["text"]]
                    order2 = base**order_source[self.Lb_order2["text"]]
                    conversion1 = self.dict_units[self.dict_mag[self.Cb_opt1.get()]][self.Cb_opt2.get()]
                    conversion2 = self.dict_units[self.dict_mag[self.Cb_opt1.get()]][self.Cb_opt3.get()]
                    self.lab_val2.config(text = "{:.1e}".format(self.val2.get()*order2))
                    self.val1.set((self.val2.get()*order2*conversion2)/(order1*conversion1))
                else:
                    self.val1.set(None)
                self.val1_old.set(self.val1.get())
                self.lab_val1.config(text = "{:.1e}".format(self.val1.get()))
        except:
            pass


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
        print('Exiting FF Explorer...')
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