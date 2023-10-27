import argparse
import os
import sys
import sqlite3
import pathlib
import subprocess
import itertools
import shutil
import mido
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog

# {{{1 variables, arguments, utility functions
home = pathlib.Path.home()
here = pathlib.Path(__file__).parent

_TESTING = False

_DBFILE =  here / "midis.db"

if _TESTING:
    _ROOTDIR = home / "Desktop" / "testmidis"
    if _DBFILE.is_file():
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

pack_left = dict(fill="both",expand=True,side="left")
pack_right= dict(fill="both",expand=True,side="right")
pack_normal= dict(fill="both",expand=True)
pack_scroll = dict(fill="y",side="right",anchor="w")

def scrollconfig(scroll,bar):
    scroll.config(yscrollcommand=bar.set)
    bar.config(command=scroll.yview)

# }}}1
# {{{1 MidiLibrarian
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
    different_notes integer,
    different_times integer,
    tracks integer,
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
                        different_notes = set()
                        different_times = set()
                        tracks = len(mid.tracks)
                        note_set = set()
                        key_sigs = set()
                        note_count = 0
                        for track in mid.tracks:
                            for message in track:
                                if message.type == "key_signature":
                                    key_sigs.add(message.key)
                                if message.type == "note_on":
                                    different_notes.add(message.note)
                                    different_times.add(message.time)
                                    note_set.add(note_d[message.note])
                                    note_count += 1

                        if not len(key_sigs):
                            key_sigs.add("NONE")
                        self.execute(
                            "insert into midis"
                            " (path,dir,name,keys,notecount,noteset,different_notes,different_times,tracks)"
                            " values (?,?,?,?,?,?,?,?,?)",(
                                path,
                                _dir,
                                name,
                                "_".join(sorted(key_sigs)),
                                note_count,
                                str(sorted(note_set)),
                                len(different_notes),
                                len(different_times),
                                tracks))
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
    def different_notes_view(self):
        return [_ANYKEY] + list(self.cu.execute("select distinct different_notes from midis order by different_notes"))
    def different_times_view(self):
        return [_ANYKEY] + list(self.cu.execute("select distinct different_times from midis order by different_times"))
    def trackcount_view(self):
        return [_ANYKEY] + list(self.cu.execute("select distinct tracks from midis order by tracks"))
    def datatree_view(self,key,notecount,different_notes,different_times,trackcount):
        whereclauses = list()
        qargs = list()
        if (
            (key == _ANYKEY) and
            (notecount == _ANYKEY) and
            (different_notes == _ANYKEY) and
            (different_times == _ANYKEY) and
            (trackcount == _ANYKEY)):
            sql = "select id,path,name from midis"
        else:
            sqlfmt = "select id,path,name from midis where {}"
            if key != _ANYKEY:
                whereclauses.append("keys=?")
                qargs.append(key)
            if notecount != _ANYKEY:
                whereclauses.append("notecount=?")
                qargs.append(notecount)
            if different_notes != _ANYKEY:
                whereclauses.append("different_notes=?")
                qargs.append(different_notes)
            if different_times != _ANYKEY:
                whereclauses.append("different_times=?")
                qargs.append(different_times)
            if trackcount != _ANYKEY:
                whereclauses.append("tracks=?")
                qargs.append(trackcount)
            sql = sqlfmt.format(" and ".join(whereclauses))
        print("sql:",sql)
        print("qargs:",qargs)
        if not qargs:
            return list(self.execute(sql))
        else:
            return list(self.execute(sql,qargs))

# }}}1
# {{{1 MidiLibrary

class MidiLibrary:
    _handle = None
    @property
    def cx(self):
        if not self._handle:
            self._handle = sqlite3.connect(
                _DBFILE,
                factory=MidiLibrarian)
        return self._handle

# }}}1
# {{{1 DifferentNotesFrame

class DifferentNotesFrame(ttk.LabelFrame):
    def update_view(self):
        if not len(self.listv.get()):
            print("DifferentNotesFrame View Update...",end="")
            self.listv.set(self.winfo_toplevel().db.cx.different_notes_view())
            print("Complete")
        else:
            print("DifferentNotesFrame View Update Skipped")
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
        self.listbox.pack(**pack_left)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.listbox,self.scrollbar)
        self.listbox.bind("<<ListboxSelect>>",self.selection_callback)

# }}}1
# {{{1 NoteCountFrame

class DifferentTimesFrame(ttk.LabelFrame):
    def update_view(self):
        if not len(self.listv.get()):
            print("DifferentTimesFrame View Update...",end="")
            self.listv.set(self.winfo_toplevel().db.cx.different_times_view())
            print("Complete")
        else:
            print("DifferentTimesFrame View Update Skipped")
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
        self.listbox.pack(**pack_left)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.listbox,self.scrollbar)
        self.listbox.bind("<<ListboxSelect>>",self.selection_callback)

# }}}1
# {{{1 NoteCountFrame

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
        self.listbox.pack(**pack_left)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.listbox,self.scrollbar)
        self.listbox.bind("<<ListboxSelect>>",self.selection_callback)

# }}}1
# {{{1 KeyFrame

class KeyFrame(ttk.LabelFrame):
    def update_view(self):
        if not len(self.listv.get()):
            print("KeyFrame View Update...",end="")
            self.listv.set(self.winfo_toplevel().db.cx.keys_view())
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
        self.listbox.pack(**pack_left)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.listbox,self.scrollbar)
        self.listbox.bind("<<ListboxSelect>>",self.selection_callback)

# }}}1
# {{{1 TrackCountFrame

class TrackCountFrame(ttk.LabelFrame):
    def update_view(self):
        if not len(self.listv.get()):
            print("TrackCountFrame View Update...",end="")
            self.listv.set(self.winfo_toplevel().db.cx.trackcount_view())
            print("Complete")
        else:
            print("TrackCountFrame View Update Skipped")
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
        self.listbox.pack(**pack_left)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.listbox,self.scrollbar)
        self.listbox.bind("<<ListboxSelect>>",self.selection_callback)

# }}}1
# {{{1 DataFrame

class DataFrame(ttk.LabelFrame):
    def __init__(self,master):
        super().__init__(master)
        self.active_item = tk.StringVar()
        self.framelabel = tk.Label(self,textvariable=self.active_item)
        self.configure(labelwidget=self.framelabel)
        self.tree = ttk.Treeview(self,show="tree",selectmode="extended")
        self.tree.pack(**pack_left)
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.pack(**pack_scroll)
        scrollconfig(self.tree,self.scrollbar)
        self.tree.bind("<<TreeviewSelect>>",self.selection_callback)
        self.tree.bind("<Double-1>",self.doubleclick_callback)
        self.tree.bind("<Control-.>",self.copy_selected_to)
    def update_view(self):
        print("DataFrame View Update")
        self.tree.delete(*self.tree.get_children())
        print("Tree Cleared")
        filterframe = self.winfo_toplevel().mainframe.filterframe
        key = filterframe.keyframe.active_item.get()
        notecount = filterframe.notecountframe.active_item.get()
        different_notes = filterframe.different_notesframe.active_item.get()
        different_times = filterframe.different_timesframe.active_item.get()
        trackcount = filterframe.trackcountframe.active_item.get()
        for oid,path,name in self.winfo_toplevel().db.cx.datatree_view(key,notecount,different_notes,different_times,trackcount):
            self.tree.insert("","end",text=name,values=(oid,path))
        self.active_item.set(
            "key(s):{} | notecount:{} | different notes:{} | different times:{} | track count:{}".format(
                key,notecount,different_notes,different_times,trackcount))
    def selection_callback(self,event):
        selection = self.tree.selection()
        print("len(selection):",len(selection))
        item_values = self.tree.item(selection,"values")
        path = item_values[1]
        self.active_item.set(path)
    def doubleclick_callback(self,event):
        selection = self.tree.selection()
        print("type(selection):",type(selection))
        for t in selection:
            item_values = self.tree.item(t,"values")
            path = item_values[1]
            print("path:",path)
            subprocess.run("explorer /select,\"{}\"".format(path),shell=True)
    def copy_selected_to(self,*event_or_none):
        t = filedialog.askdirectory()
        print("t:",t)
        if not t:
            return
        target = pathlib.Path(t).resolve()
        print("target:",target)
        if not target.is_dir():
            return
        selected_files = list()
        for iid in self.tree.selection():
            item_values = self.tree.item(iid,"values")
            path = item_values[1]
            selected_files.append(pathlib.Path(path))
        for p in selected_files:
            if p.is_file():
                print("p:",p)
                shutil.copy(p,target)
    def move_selected_to(self,*event_or_none):
        t = filedialog.askdirectory()
        print("t:",t)
        if not t:
            return
        target = pathlib.Path(t).resolve()
        print("target:",target)
        if not target.is_dir():
            return
        selected_files = list()
        for iid in self.tree.selection():
            item_values = self.tree.item(iid,"values")
            path = item_values[1]
            selected_files.append(pathlib.Path(path))
        for p in selected_files:
            if p.is_file():
                print("p:",p)
                shutil.move(p,target)

# }}}1
# {{{1 ActionFrame

class ActionFrame(ttk.LabelFrame):
    def __init__(self,master):
        super().__init__(master)
        self.copybutton = tk.Button(self,
                                    text="Copy to...",
                                    command=self.winfo_toplevel().mainframe.dataframe.copy_selected_to)
        self.copybutton.pack()
        self.movebutton = tk.Button(self,
                                    text="Move to...",
                                    command=self.winfo_toplevel().mainframe.dataframe.move_selected_to)
        self.movebutton.pack()
        

# }}}1
# {{{1 FilterFrame

class FilterFrame(ttk.LabelFrame):
    def __init__(self,master):
        super().__init__(master)
        self.configure(text="Filters")

        self.keylabel = tk.Label(self,text="Key Signature(s)")
        self.keylabel.pack()
        self.keyframe = KeyFrame(self)
        self.keyframe.pack(**pack_normal)

        self.notecountlable = tk.Label(self,text="Total Notes")
        self.notecountlable.pack()
        self.notecountframe = NoteCountFrame(self)
        self.notecountframe.pack(**pack_normal)

        self.diffnoteslabel = tk.Label(self,text="Distinct Notes")
        self.diffnoteslabel.pack()
        self.different_notesframe = DifferentNotesFrame(self)
        self.different_notesframe.pack(**pack_normal)

        self.diffnoteslabel = tk.Label(self,text="Distinct Times")
        self.diffnoteslabel.pack()
        self.different_timesframe = DifferentTimesFrame(self)
        self.different_timesframe.pack(**pack_normal)

        self.trackcountlabel = tk.Label(self,text="Track Count")
        self.trackcountlabel.pack()
        self.trackcountframe = TrackCountFrame(self)
        self.trackcountframe.pack(**pack_normal)


# }}}1
# {{{1 MainFrame

class MainFrame(tk.Frame):
    def __init__(self,master):
        super().__init__(master)
        self.filterframe = FilterFrame(self)
        self.filterframe.pack(fill="y",side="left")
        self.dataframe = DataFrame(self)
        self.dataframe.pack(**pack_right)

# }}}1
# {{{1 App

class App(tk.Tk):
    def update_ui(self):
        print("Updating UI")
        ff = self.mainframe.filterframe
        ff.keyframe.update_view()
        ff.notecountframe.update_view()
        ff.different_notesframe.update_view()
        ff.different_timesframe.update_view()
        ff.trackcountframe.update_view()
        self.mainframe.dataframe.update_view()
    def __init__(self):
        super().__init__()
        self.geometry("1600x1200")
        self.topframe = tk.Frame(self)
        self.topframe.pack(fill="both",expand=True,side="top")
        self.bottomframe = tk.Frame(self)
        self.bottomframe.pack(fill="x",expand=False,side="bottom")
        self.mainframe = MainFrame(self.topframe)
        self.mainframe.pack(**pack_normal)
        self.actionframe = ActionFrame(self.bottomframe)
        self.actionframe.pack(fill="both",expand=True)
        self.db = MidiLibrary()
        if ns.scan:
            self.db.cx.populate_from(ns.rootdir)
        self.update_ui()
        ff = self.mainframe.filterframe
        ff.keyframe.listbox.selection_set(0)
        ff.keyframe.listbox.event_generate("<<ListboxSelect>>")

        ff.notecountframe.listbox.selection_set(0)
        ff.notecountframe.listbox.event_generate("<<ListboxSelect>>")

        ff.different_notesframe.listbox.selection_set(0)
        ff.different_notesframe.listbox.event_generate("<<ListboxSelect>>")

        ff.different_timesframe.listbox.selection_set(0)
        ff.different_timesframe.listbox.event_generate("<<ListboxSelect>>")

        ff.trackcountframe.listbox.selection_set(0)
        ff.trackcountframe.listbox.event_generate("<<ListboxSelect>>")
        
        list(map(print,self.db.cx.iterdump()))
        print("Remember: run with --scan at least once!")
# }}}1

if __name__ == "__main__":
    App().mainloop()

