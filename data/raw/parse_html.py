import json, re, html as H
from html.parser import HTMLParser

RAW="data/raw"
manifest=json.load(open(RAW+"/rendered_manifest.json"))

# ---- minimal DOM ----
class Node:
    __slots__=("tag","attrs","children","parent","text")
    def __init__(self,tag,attrs=None,parent=None):
        self.tag=tag; self.attrs=dict(attrs or {}); self.children=[]; self.parent=parent; self.text=""

VOID={"br","img","hr","meta","link","input","wbr","col"}

class DOM(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root=Node("root"); self.cur=self.root
    def handle_starttag(self,tag,attrs):
        if tag in VOID:
            n=Node(tag,attrs,self.cur); self.cur.children.append(n); return
        n=Node(tag,attrs,self.cur); self.cur.children.append(n); self.cur=n
    def handle_startendtag(self,tag,attrs):
        n=Node(tag,attrs,self.cur); self.cur.children.append(n)
    def handle_endtag(self,tag):
        # walk up to matching tag
        node=self.cur
        while node is not None and node.tag!=tag:
            node=node.parent
        if node is not None and node.parent is not None:
            self.cur=node.parent
    def handle_data(self,data):
        t=Node("#text",parent=self.cur); t.text=data; self.cur.children.append(t)

def text_of(node):
    if node.tag=="#text": return node.text
    if node.tag in ("script","style"): return ""
    if node.tag=="br": return " "
    if node.tag=="sup":  # footnote refs
        cls=node.attrs.get("class","")
        if "reference" in cls: return ""
    parts=[]
    for c in node.children:
        parts.append(text_of(c))
    s="".join(parts)
    return s

def norm(s):
    s=s.replace("–","-").replace("—","-").replace("−","-")
    s=s.replace("\xa0"," ")
    s=re.sub(r"\s+"," ",s).strip()
    return s

def iter_tables_with_headings(root):
    """DFS; yield (heading_chain, table_node)."""
    chain={}  # level->text
    out=[]
    def walk(node):
        for c in node.children:
            if c.tag in ("h2","h3","h4","h5","h6"):
                lvl=int(c.tag[1])
                # headline text: prefer span.mw-headline
                htext=None
                for d in c.children:
                    if d.tag=="span" and "mw-headline" in d.attrs.get("class",""):
                        htext=norm(text_of(d)); break
                if htext is None:
                    htext=norm(text_of(c)).replace("[edit | edit source]","").strip()
                chain[lvl]=htext
                for k in [k for k in chain if k>lvl]: del chain[k]
            elif c.tag=="table":
                ch=[chain[k] for k in sorted(chain)]
                out.append((list(ch), c))
                walk(c)  # nested tables
            else:
                walk(c)
    walk(root)
    return out

def get_int_attr(node,name,default=1):
    v=node.attrs.get(name)
    if not v: return default
    m=re.match(r"\d+",v.strip())
    return int(m.group(0)) if m else default

def table_grid(table):
    """Build a 2D grid honoring colspan/rowspan. Each cell: (text, is_header)."""
    # gather rows from direct tr (within thead/tbody too)
    rows=[]
    def collect_rows(n):
        for c in n.children:
            if c.tag=="tr": rows.append(c)
            elif c.tag in ("thead","tbody","tfoot"): collect_rows(c)
    collect_rows(table)
    grid={}  # (r,c)->(text,is_header)
    occ=set()
    maxc=0
    for r,tr in enumerate(rows):
        c=0
        for cell in tr.children:
            if cell.tag not in ("td","th"): continue
            while (r,c) in occ: c+=1
            cs=get_int_attr(cell,"colspan"); rs=get_int_attr(cell,"rowspan")
            txt=norm(text_of(cell))
            is_h=(cell.tag=="th")
            for dr in range(rs):
                for dc in range(cs):
                    occ.add((r+dr,c+dc))
                    grid[(r+dr,c+dc)]=(txt,is_h)
            c+=cs
            maxc=max(maxc,c)
    nrows=len(rows)
    return grid,nrows,maxc

def is_level_header(h):
    hl=h.lower()
    return ("level" in hl) and ("xp" not in hl) and ("experience" not in hl)

def is_xp_header(h):
    hl=h.lower().replace(" ","")
    return ("xp/h" in hl) or ("xp/hr" in hl) or ("experienceperhour" in hl) or ("exp/h" in hl) or ("xpperhour" in hl)

NUM_RE=re.compile(r"[\d][\d,\.]*")

def parse_num_token(tok):
    tok=tok.strip()
    mult=1
    if tok and tok[-1] in "kK": mult=1000; tok=tok[:-1]
    elif tok and tok[-1] in "mM": mult=1000000; tok=tok[:-1]
    tok=tok.replace(",","")
    if not re.match(r"^\d+(\.\d+)?$",tok): return None
    v=float(tok) if "." in tok else int(tok)
    if mult>1: v=v*mult
    return int(v) if isinstance(v,float) and v.is_integer() else v

def parse_xp_cell(s):
    s=norm(s)
    if not s: return None
    if s.lower() in ("n/a","na","-","varies","tbd","none","–","—"): return None
    toks=re.findall(r"[\d][\d,\.]*\s*[kKmM]?", s)
    vals=[]
    for t in toks:
        v=parse_num_token(t.replace(" ",""))
        if v is not None: vals.append(v)
    if not vals: return None
    if len(vals)==1: return {"value":vals[0],"raw":s}
    return {"low":min(vals),"high":max(vals),"raw":s}

def parse_level_cell(s):
    s=norm(s)
    nums=re.findall(r"\d+", s.replace(",",""))
    if not nums: return None
    nums=[int(x) for x in nums]
    # ignore absurd values (xp amounts) - levels are 1..120ish; but cell might be just a level
    if len(nums)==1:
        return [nums[0],nums[0]]
    return [min(nums),max(nums)]

def build_column_headers(grid,nrows,ncols):
    """Detect contiguous header rows from top; build combined column labels."""
    header_row_count=0
    for r in range(nrows):
        cells=[grid.get((r,c)) for c in range(ncols)]
        present=[x for x in cells if x is not None]
        if not present: break
        hfrac=sum(1 for x in present if x[1])/len(present)
        if hfrac>=0.5: header_row_count=r+1
        else: break
    if header_row_count==0:
        return None,0
    cols=[]
    for c in range(ncols):
        parts=[]
        for r in range(header_row_count):
            cell=grid.get((r,c))
            if cell and cell[0] and (not parts or parts[-1]!=cell[0]):
                parts.append(cell[0])
        cols.append(" ".join(parts).strip())
    return cols,header_row_count

def parse_table_node(table, chain, family, skill):
    grid,nrows,ncols=table_grid(table)
    if nrows==0 or ncols==0: return []
    cols,hrows=build_column_headers(grid,nrows,ncols)
    if not cols: return []
    level_idx=None; xp_cols=[]
    for i,h in enumerate(cols):
        if level_idx is None and is_level_header(h): level_idx=i
        if is_xp_header(h): xp_cols.append((i,h))
    if level_idx is None or not xp_cols: return []
    method=chain[-1] if chain else None
    level_header=cols[level_idx]
    recs=[]
    for r in range(hrows,nrows):
        lc=grid.get((r,level_idx))
        if not lc: continue
        band=parse_level_cell(lc[0])
        if not band: continue
        # sanity: level band within plausible skill range
        if band[0]<1 or band[1]>200: continue
        for (ci,hname) in xp_cols:
            xc=grid.get((r,ci))
            if not xc: continue
            xp=parse_xp_cell(xc[0])
            if not xp: continue
            # drop if value looks like a level (<200) AND header is bare? keep; xp/h are usually >1000
            recs.append({
                "skill":skill,"account_family":family,
                "level_band":band,"method":method,
                "method_path":" / ".join(chain) if chain else None,
                "level_column":level_header,
                "xp_hr":xp,"xp_hr_column":hname,
            })
    return recs

def process(html_file, family, skill):
    html=open(html_file).read()
    dom=DOM(); dom.feed(html)
    tabs=iter_tables_with_headings(dom.root)
    out=[]
    for chain,tab in tabs:
        out.extend(parse_table_node(tab,chain,family,skill))
    return out

if __name__=="__main__":
    import sys
    mode=sys.argv[1] if len(sys.argv)>1 else "all"
    if mode=="test":
        for title in ["Pay-to-play Crafting training","Pay-to-play Woodcutting training","Herblore training","Pay-to-play Fishing training","Free-to-play Magic training"]:
            info=manifest[title]
            recs=process(info["html_file"],info["family"],info["skill"])
            print(f"\n### {title}: {len(recs)}")
            seen=set()
            for r in recs:
                k=(r['method'],r['xp_hr_column'])
                if k in seen: continue
                seen.add(k)
                print(f"  {r['method']!r} | col={r['xp_hr_column']!r}")
    else:
        allrecs=[]; per={}
        for title,info in manifest.items():
            if title=="Theoretical experience rates": continue
            recs=process(info["html_file"],info["family"],info["skill"])
            for r in recs:
                r["_source_title"]=info["actual_title"]; r["_source_file"]=info["html_file"]
            per[title]=len(recs); allrecs.extend(recs)
        print("TOTAL",len(allrecs))
        fams={}; sk={}
        for r in allrecs:
            fams[r["account_family"]]=fams.get(r["account_family"],0)+1
            sk.setdefault(r["account_family"],set()).add(r["skill"])
        print("fams",fams)
        for f in("main","f2p","ironman"):
            print(f" {f} skills({len(sk.get(f,set()))}):",sorted(sk.get(f,set())))
        print("ZERO:",[t for t,c in per.items() if c==0])
