import pathlib,argparse,os,sys,sqlite3,mido,subprocess
import tkinter as tk
import tkinter.ttk as ttk
from itertools import cycle

home = pathlib.Path.home()
here = pathlib.Path(__file__).parent
_TESTING = True
# _TESTING = False
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
    def data_with_key(self,key):
        return list(self.cu.execute("select name from midis where keys=?",(key,)))


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
        self.keys.set(db.cx.distinct_keys())
        active_key = self.active_key.get()
        if active_key:
            print("active_key:",active_key)
            self.data.set(db.cx.data_with_key(active_key))
        else:
            print("no active key")

    def keylist_select(self,event):
        index = self.keylist.curselection()
        if len(index):
            item = self.keylist.get(index[0])
            self.active_key.set(item)
        self.update_ui()

    def datalist_select(self,event):
        index = self.datalist.curselection()
        if len(index):
            item = self.datalist.get(index[0])
            self.active_data.set(item)
        self.update_ui()

    def data_action(self):
        data = self.active_data.get()
        print("data:",data)
        subprocess.run("explorer /select,\"{}\"".format(data),shell=True)


    def __init__(self):
        super().__init__()
        self.keys = tk.StringVar()
        self.data = tk.StringVar()
        self.active_key = tk.StringVar()
        self.active_data = tk.StringVar()

        self.activekeylabel = tk.Label(self,textvariable=self.active_key)
        self.activedatalabel = tk.Button(self,command=self.data_action,textvariable=self.active_data)
        self.mainframe = ttk.LabelFrame(self,text="Midi File Data")
        self.mainframe.pack(fill="both",expand=True)
        self.keyframe = ttk.LabelFrame(self.mainframe,labelwidget=self.activekeylabel)
        self.keyframe.pack(fill="both",expand=True,side="left")
        self.dataframe = ttk.LabelFrame(self.mainframe,labelwidget=self.activedatalabel)
        self.dataframe.pack(fill="both",expand=True,side="right")
        self.keylist = tk.Listbox(self.keyframe,listvariable=self.keys)
        self.keylist.pack(fill="both",expand=True,side="left")
        self.keylistscroll = tk.Scrollbar(self.keyframe)
        self.keylistscroll.pack(fill="y",side="right",anchor="w")
        self.keylist.configure(yscrollcommand=self.keylistscroll.set)
        self.keylistscroll.configure(command=self.keylist.yview)
        self.datalist = tk.Listbox(self.dataframe,listvariable=self.data,width=72)
        self.datalist.pack(fill="both",expand=True,side="left")
        self.datalistscroll = tk.Scrollbar(self.dataframe)
        self.datalistscroll.pack(fill="y",side="right",anchor="w")
        self.datalist.configure(yscrollcommand=self.datalistscroll.set)
        self.datalistscroll.configure(command=self.datalist.yview)
        self.keylist.bind("<<ListboxSelect>>",self.keylist_select)
        self.datalist.bind("<<ListboxSelect>>",self.datalist_select)
        self.update_ui()


if __name__ == "__main__":
    db = MidiLibrary()
    if ns.scan:
        db.cx.populate_from(ns.rootdir)
    app = App()
    app.mainloop()

