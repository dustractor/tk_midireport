import argparse
import os
import sys
import sqlite3
import pathlib
import subprocess
import itertools
import mido
import tkinter as tk
import tkinter.ttk as ttk

home = pathlib.Path.home()
here = pathlib.Path(__file__).parent

# _TESTING = True
_TESTING = False

_DBFILE =  here / "midis.db"

if _TESTING:
    _ROOTDIR = home / "Desktop" / "testmidis"
    _DBFILE.unlink()
else:
    _ROOTDIR = home /"Documents"/"Image-Line"/"FL Studio"/"Presets"/"Scores" 

args = argparse.ArgumentParser()

args.add_argument("--scan",action="store_true")
args.add_argument("--rootdir",default=_ROOTDIR)

ns = args.parse_args()

note_d = {a:b for (a,b) in zip(
    range(128),
    itertools.cycle(["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"])
)}

_ANYKEY = "*ANY*"

class MidiLibrarian(sqlite3.Connection):
    ddl = """
    create table if not exists midis (
    id integer primary key,
    path text,
    dir text,
    name text,
    keys text,
    notecount integer,
    noteset text,
    errors text,
    unique (path) on conflict replace);
    """
    def __init__(self,name,**kwargs):
        super().__init__(name,**kwargs)
        self.executescript(self.ddl)
        self.commit()
    @property
    def cu(self):
        cu = self.cursor()
        cu.row_factory = lambda c,r:r[0]
        return cu
    def populate_from(self,path):
        for r,ds,fs in os.walk(path):
            root = pathlib.Path(r)
            print("root:",root)
            for f in fs:
                if f.endswith(".mid"):
                    error = False
                    fpath = root/f
                    print("\tfpath:",fpath)
                    path = str(fpath)
                    _dir = str(fpath.parent)
                    name = str(fpath.stem)
                    try:
                        mid = mido.MidiFile(fpath)
                    except OSError:
                        error = str(sys.exc_info()[1])
                    if not error:
                        note_set = set()
                        key_sigs = set()
                        note_count = 0
                        for track in mid.tracks:
                            for message in track:
                                if message.type == "key_signature":
                                    key_sigs.add(message.key)
                                if message.type == "note_on":
                                    note_set.add(note_d[message.note])
                                    note_count += 1
                        if not len(key_sigs):
                            key_sigs.add("NONE")
                        self.execute(
                            "insert into midis"
                            " (path,dir,name,keys,notecount,noteset)"
                            " values (?,?,?,?,?,?)",
                            (
                                path,
                                _dir,
                                name,
                                "_".join(sorted(key_sigs)),
                                note_count,
                                str(sorted(note_set)))
                            )
                    else:
                        self.execute(
                            "insert into midis"
                            " (path,dir,name,errors) values (?,?,?,?)",
                            (
                                path,
                                _dir,
                                name,
                                error)
                            )
        self.commit()
    def keys_view(self):
        return [_ANYKEY] + list(self.cu.execute("select distinct keys from midis order by keys"))
    def notecounts_view(self):
        return [_ANYKEY] + list(self.cu.execute("select distinct notecount from midis order by notecount"))
    def datatree_view(self,key,notecount):
        print("[[[key,notecount:",key,notecount,"]]]")
        if key == _ANYKEY and notecount == _ANYKEY:
            print("any key/any notecount")
            return list(self.execute("select id,path,name from midis"))
        elif key == _ANYKEY:
            print("any key")
            return list(self.execute("select id,path,name from midis where notecount=?",(notecount,)))
        elif notecount == _ANYKEY:
            print("any notecount")
            return list(self.execute("select id,path,name from midis where keys=?",(key,)))
        else:
            print("key,notecount:",key,notecount)
            return list(self.execute("select id,path,name from midis where keys=? and notecount=?",(key,notecount)))



class MidiLibrary:
    _handle = None
    @property
    def cx(self):
        if not self._handle:
            self._handle = sqlite3.connect(
                _DBFILE,
                factory=MidiLibrarian)
        return self._handle


pack_l = dict(fill="both",expand=True,side="left")
pack_r= dict(fill="both",expand=True,side="right")
pack_n= dict(fill="both",expand=True)
pack_scroll = dict(fill="y",side="right",anchor="w")

def scrollconfig(scroll,bar):
    scroll.config(yscrollcommand=bar.set)
    bar.config(command=scroll.yview)


class NoteCountFrame(ttk.LabelFrame):
    def update_view(self):
        if not len(self.listv.get()):
            print("NoteCountFrame View Update...",end="")
            self.listv.set(self.winfo_toplevel().db.cx.notecounts_view())
            # self.listbox.selection_set(0)
            print("Complete")
        else:
            print("NoteCountFrame View Update Skipped")
    def selection_callback(self,event):
        index = self.listbox.curselection()
        if len(index):
            item = self.listbox.get(index[0])
            self.active_item.set(item)
            self.winfo_toplevel().update_ui()
    def __init__(self,master):
        super().__init__(master)
        self.listv = tk.StringVar()
        self.active_item = tk.StringVar()
        self.framelabel = tk.Label(self,textvariable=self.active_item)
        self.configure(labelwidget=self.framelabel)
        self.listbox = tk.Listbox(self,listvariable=self.listv,width=16)
        self.listbox.pack(**pack_l)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.listbox,self.scrollbar)
        self.listbox.bind("<<ListboxSelect>>",self.selection_callback)


class KeyFrame(ttk.LabelFrame):
    def update_view(self):
        if not len(self.listv.get()):
            print("KeyFrame View Update...",end="")
            self.listv.set(self.winfo_toplevel().db.cx.keys_view())
            # self.listbox.selection_set(0)
            print("Complete")
        else:
            print("KeyFrame View Update Skipped")
    def selection_callback(self,event):
        index = self.listbox.curselection()
        if len(index):
            item = self.listbox.get(index[0])
            self.active_item.set(item)
            self.winfo_toplevel().update_ui()
    def __init__(self,master):
        super().__init__(master)
        self.listv = tk.StringVar()
        self.active_item = tk.StringVar()
        self.framelabel = tk.Label(self,textvariable=self.active_item)
        self.configure(labelwidget=self.framelabel)
        self.listbox = tk.Listbox(self,listvariable=self.listv,width=16)
        self.listbox.pack(**pack_l)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.listbox,self.scrollbar)
        self.listbox.bind("<<ListboxSelect>>",self.selection_callback)


class DataFrame(ttk.LabelFrame):
    def update_view(self):
        print("DataFrame View Update")
        self.tree.delete(*self.tree.get_children())
        print("Tree Cleared")
        key = self.master.filterframe.keyframe.active_item.get()
        notecount = self.master.filterframe.notecountframe.active_item.get()
        for oid,path,name in self.winfo_toplevel().db.cx.datatree_view(key,notecount):
            self.tree.insert("","end",text=name,values=(oid,path))
        self.active_item.set("key(s):{} notecount:{}".format(key,notecount))
    def selection_callback(self,event):
        selection = self.tree.selection()
        item_values = self.tree.item(selection,"values")
        path = item_values[1]
        self.active_item.set(path)
    def doubleclick_callback(self,event):
        selection = self.tree.selection()
        item_values = self.tree.item(selection,"values")
        path = item_values[1]
        # self.active_item.set(path)
        print("path:",path)
        subprocess.run("explorer /select,\"{}\"".format(path),shell=True)

    def __init__(self,master):
        super().__init__(master)
        self.active_item = tk.StringVar()
        self.framelabel = tk.Label(self,textvariable=self.active_item)
        self.configure(labelwidget=self.framelabel)
        self.tree = ttk.Treeview(self,show="tree")
        self.tree.pack(**pack_l)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.tree,self.scrollbar)
        self.tree.bind("<<TreeviewSelect>>",self.selection_callback)
        self.tree.bind("<Double-1>",self.doubleclick_callback)


class FilterFrame(ttk.LabelFrame):
    def __init__(self,master):
        super().__init__(master)
        self.configure(text="Filters")
        self.keyframe = KeyFrame(self)
        self.keyframe.pack(**pack_n)
        self.notecountframe = NoteCountFrame(self)
        self.notecountframe.pack(**pack_n)


class MainFrame(tk.Frame):
    def __init__(self,master):
        super().__init__(master)
        self.filterframe = FilterFrame(self)
        self.filterframe.pack(fill="y",side="left")
        self.dataframe = DataFrame(self)
        self.dataframe.pack(**pack_r)


class App(tk.Tk):
    def update_ui(self):
        print("Updating UI")
        self.mainframe.filterframe.keyframe.update_view()
        self.mainframe.filterframe.notecountframe.update_view()
        self.mainframe.dataframe.update_view()
    def __init__(self):
        super().__init__()
        self.geometry("1024x768")
        self.mainframe = MainFrame(self)
        self.mainframe.pack(**pack_n)
        self.db = MidiLibrary()
        if ns.scan:
            self.db.cx.populate_from(ns.rootdir)
        self.update_ui()
        self.mainframe.filterframe.keyframe.listbox.selection_set(0)
        self.mainframe.filterframe.keyframe.listbox.event_generate("<<ListboxSelect>>")
        self.mainframe.filterframe.notecountframe.listbox.selection_set(0)
        self.mainframe.filterframe.notecountframe.listbox.event_generate("<<ListboxSelect>>")
        
        # list(map(print,self.db.cx.iterdump()))


if __name__ == "__main__":
    App().mainloop()

