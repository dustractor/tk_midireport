import pathlib,argparse,os,sys,sqlite3,mido,subprocess
import tkinter as tk
import tkinter.ttk as ttk
from itertools import cycle

home = pathlib.Path.home()
here = pathlib.Path(__file__).parent
# _TESTING = True
_TESTING = False
_DBFILE =  here / "midis.db"
_DEFAULTROOTDIR = home /"Documents"/"Image-Line"/"FL Studio"/"Presets"/"Scores" 
_TESTINGROOT = home / "Desktop" / "testmidis"

args = argparse.ArgumentParser()

if _TESTING:
    if _DBFILE.is_file():
        _DBFILE.unlink()
        print("removed database file")
    args.add_argument("--scan",default=True)
    args.add_argument("--rootdir",default=_TESTINGROOT)
else:
    args.add_argument("--scan",action="store_true")
    args.add_argument("--rootdir",default=_DEFAULTROOTDIR)

ns = args.parse_args()

note_d = {a:b for (a,b) in zip(
    range(128),
    cycle(["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]))}


_ANYKEY = "*ANY*"
_NOTECOUNTS = ["0","1-10","11-100","101-1000",">1000"]
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
            for f in fs:
                if f.endswith(".mid"):
                    error = False
                    fpath = root/f
                    path = str(fpath)
                    _dir = str(fpath.parent)
                    name = str(fpath.stem)
                    print("path,_dir,name:",path,_dir,name)
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
                        self.execute("insert into midis (path,dir,name,keys,notecount,noteset) values (?,?,?,?,?,?)",
                        (path,_dir,name,
                         "_".join(sorted(key_sigs)),
                         str(sorted(note_set)),
                         note_count))
                    else:
                        self.execute("insert into midis (path,dir,name,errors) values (?,?,?,?)",
                                   (path,_dir,name,
                                    error))
        self.commit()

    def distinct_keys(self):
        return list(self.cu.execute("select distinct keys from midis"))
    def datatree_view(self,key):
        if key == _ANYKEY:
            return list(self.execute("select id,path,name from midis"))
        else:
            return list(self.execute("select id,path,name from midis where keys=?",(key,)))


class MidiLibrary:
    _handle = None

    @property
    def cx(self):
        if not self._handle:
            self._handle = sqlite3.connect(
                _DBFILE,
                factory=MidiLibrarian)
        return self._handle


class App(tk.Tk):
    def update_ui(self):
        self.keys.set([_ANYKEY]+list(db.cx.distinct_keys()))
        active_key = self.active_key.get()
        if active_key:
            self.fill_datatree(active_key)
        else:
            self.clear_datatree()

    def clear_datatree(self):
        self.datatree.delete(*self.datatree.get_children())

    def fill_datatree(self,key):
        self.clear_datatree()
        for t in db.cx.datatree_view(key):
            self.datatree.insert("","end",text=t[2],values=(t[0],t[1]))

    def keylist_select(self,event):
        index = self.keylist.curselection()
        if len(index):
            item = self.keylist.get(index[0])
            self.active_key.set(item)
        self.update_ui()

    def datatree_select(self,event):
        selection = self.datatree.selection()
        t = self.datatree.item(selection,"values")
        path = t[1]
        self.active_data.set(path)

    def notectlist_select(self,event):
        index = self.notectlist.curselection()
        if len(index):
            item = self.notectlist.get(index[0])
            self.active_notecount.set(item)
        self.update_ui()

    def data_action(self):
        data = self.active_data.get()
        print("data:",data)
        subprocess.run("explorer /select,\"{}\"".format(data),shell=True)

    def __init__(self):
        super().__init__()
        self.keys = tk.StringVar()
        self.active_key = tk.StringVar()
        self.active_data = tk.StringVar()
        self.active_notecount = tk.StringVar()
        self.notecounts = tk.StringVar()
        self.notecounts.set(_NOTECOUNTS)
        

        self.activekeylabel = tk.Label(self,textvariable=self.active_key)
        self.activedatalabel = tk.Button(self,command=self.data_action,textvariable=self.active_data)
        self.activenotectlabel = tk.Label(self,textvariable=self.active_notecount)
        self.mainframe = ttk.LabelFrame(self,text="Midi File Data")
        self.mainframe.pack(fill="both",expand=True)
        self.filterframe = ttk.Frame(self.mainframe)
        self.filterframe.pack(fill="both",expand=True,side="left")
        self.keyframe = ttk.LabelFrame(self.filterframe,labelwidget=self.activekeylabel)
        self.keyframe.pack(fill="both",expand=True)
        self.notectframe = ttk.LabelFrame(self.filterframe,labelwidget=self.activenotectlabel)
        self.notectframe.pack(fill="both",expand=True)
        self.dataframe = ttk.LabelFrame(self.mainframe,labelwidget=self.activedatalabel)
        self.dataframe.pack(fill="both",expand=True,side="right")
        self.keylist = tk.Listbox(self.keyframe,listvariable=self.keys)
        self.keylist.pack(fill="both",expand=True,side="left")
        self.keylistscroll = tk.Scrollbar(self.keyframe)
        self.keylistscroll.pack(fill="y",side="right",anchor="w")
        self.keylist.configure(yscrollcommand=self.keylistscroll.set)
        self.keylistscroll.configure(command=self.keylist.yview)
        self.notectlist = tk.Listbox(self.notectframe,listvariable=self.notecounts)
        self.notectlist.pack(fill="both",expand=True,side="left")
        self.notectscroll = tk.Scrollbar(self.notectframe)
        self.notectscroll.pack(fill="y",side="right",anchor="w")
        self.notectlist.configure(yscrollcommand=self.notectscroll.set)
        self.notectscroll.configure(command=self.notectlist.yview)
        self.datatree = ttk.Treeview(self.dataframe)
        self.datatree.pack(fill="both",expand=True,side="left")
        self.datatreescroll = tk.Scrollbar(self.dataframe)
        self.datatreescroll.pack(fill="y",side="right",anchor="w")
        self.datatree.configure(yscrollcommand=self.datatreescroll.set,show="tree")
        self.datatreescroll.configure(command=self.datatree.yview)
        self.keylist.bind("<<ListboxSelect>>",self.keylist_select)
        self.datatree.bind("<<TreeviewSelect>>",self.datatree_select)
        self.notectlist.bind("<<ListboxSelect>>",self.notectlist_select)
        self.update_ui()


if __name__ == "__main__":
    db = MidiLibrary()
    if ns.scan:
        db.cx.populate_from(ns.rootdir)
    app = App()
    app.mainloop()

