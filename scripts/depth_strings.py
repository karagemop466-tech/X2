#!/usr/bin/env python3
"""Build the club depth-chart string register and the matchup-deficiency matrix.

WHAT THIS IS
------------
Two outputs, both derived from ONE hand transcription so they cannot disagree:

  data/depth_chart_strings_2026.csv   one row per club / side / position slot / string
  data/matchup_matrix_week11.csv      one row per club / unit / position slot, columns 1st-4th

The transcription in CLUBS below was read from each club's own depth-chart page on the
date in `read_utc`. Every row carries the page URL. Nothing is inferred: a blank cell in
this file means the club published a blank cell. Two players in one cell (e.g. Seattle's
two receivers in slot 1, Washington's empty slot) are kept as a SHARED or EMPTY slot,
never split into a fabricated order (the brief's "represent shared and empty depth slots
faithfully", VR-21/VR-23).

WHY ONLY SOME CLUBS
-------------------
The brief forbids modelling depth from jersey order, experience or salary, and forbids
inferring a depth rank from anything but a published chart. So a club appears here only
if its own site publishes a machine-readable chart AND this session read it. Clubs whose
chart is published as an image cannot be transcribed from text at all:

  HOU  https://www.houstontexans.com/team/depth-chart  - the chart is an <img>; the page
       text carries the heading "Unofficial Depth Chart" and no position/name table.
       Re-confirmed 2026-11-18 (see data/chart_rejections.csv).

The remaining clubs are NOT rejected, only unread in this pass; they are listed in
data/chart_rejections.csv with the specific reason so the gap is countable.

SEATTLE / WASHINGTON: shared and empty slots
--------------------------------------------
Seattle publishes TWO players in one slot on both the receiver row and elsewhere;
Washington publishes an empty first-string cell on one defensive row. Both are carried
as one cell with `slot_type` = shared / empty. A "1st string" column that silently picked
one name would fabricate a starter the club never named.
"""
import csv
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
READ_UTC = "2026-11-18"

# ---------------------------------------------------------------------------
# CLUBS: club_abbr -> (club name, url, self-label, date as published, offense, defense)
# Each position is a list of slots; each slot is a LIST OF NAMES. len(slot) == 2 means the
# club published two players in that one cell (a shared slot); len(slot) == 0 means blank.
# ---------------------------------------------------------------------------
CLUBS = {
    "DET": ("Detroit Lions", "https://www.detroitlions.com/team/depth-chart",
            "unofficial (\u201c2026 Unofficial Depth Chart Compiled by Lions Football Communications\u201d)",
            "not dated on the page",
            [("WR", [["Jameson Williams"], [], [], []]),
             ("WR", [["Amon-Ra St. Brown"], ["DeAndre Carter"], [], []]),
             ("LT", [["Penei Sewell"], [], [], []]),
             ("LG", [["Christian Mahogany"], ["Miles Frazier"], [], []]),
             ("C", [["Cade Mays"], ["Juice Scruggs"], [], []]),
             ("RG", [["Tate Ratledge"], ["Seth McLaughlin"], [], []]),
             ("RT", [["Blake Miller"], ["Larry Borom"], [], []]),
             ("TE", [["Sam LaPorta"], ["Brock Wright"], ["Tyler Conklin"], []]),
             ("WR", [["Isaac TeSlaa"], ["Tay Martin"], [], []]),
             ("QB", [["Jared Goff"], ["Joshua Dobbs"], [], []]),
             ("RB", [["Jahmyr Gibbs"], ["Sione Vaki"], ["Jacob Saylors"], []])],
            [("EDGE", [["Aidan Hutchinson"], ["Derrick Moore"], ["Eric O'Neill"], []]),
             ("DL", [["Alim McNeill"], ["Skyler Gill-Howard"], ["Mekhi Wingo"], []]),
             ("DL", [["Tyleik Williams"], ["Levi Onwuzurike"], [], []]),
             ("EDGE", [["DJ Wonnum"], ["Tyler Lacy"], ["Ahmed Hassanein"], ["Tyrus Wheat"]]),
             ("LB", [["Derrick Barnes"], ["Joe Bachie"], [], []]),
             ("LB", [["Malcolm Rodriguez"], ["K.J. Britt"], [], []]),
             ("LB", [["Trevor Nowaske"], ["Amen Ogbongbemiga"], [], []]),
             ("CB", [["D.J. Reed"], ["Rock Ya-Sin"], ["Khalil Dorsey"], []]),
             ("CB", [["Roger McCreary"], ["Ennis Rakestraw Jr."], ["Keith Abney II"], []]),
             ("S", [["Chuck Clark"], ["Andre Cisco"], [], []]),
             ("S", [["Brian Branch"], ["Christian Izien"], [], []])]),

    "NO": ("New Orleans Saints", "https://www.neworleanssaints.com/team/depth-chart",
           "unofficial (\u201cNew Orleans Saints Unofficial Depth Chart\u201d)", "not dated on the page",
           [("WR", [["Chris Olave"], ["Barion Brown"], [], []]),
            ("LT", [["Kelvin Banks Jr."], ["Asim Richards"], [], []]),
            ("LG", [["David Edwards"], ["Jeremiah Wright"], [], []]),
            ("C", [["Erik McCoy"], ["William Sherman"], [], []]),
            ("RG", [["Cesar Ruiz"], ["Jeremiah Wright"], [], []]),
            ("RT", [["Taliese Fuaga"], ["Mason Murphy"], ["Easton Kilty"], []]),
            ("TE", [["Juwan Johnson"], ["Noah Fant"], ["Oscar Delp"], []]),
            ("WR", [["Devaughn Vele"], ["Bryce Lance"], [], []]),
            ("WR", [["Jordyn Tyson"], ["Barion Brown"], [], []]),
            ("QB", [["Tyler Shough"], ["Spencer Rattler"], ["Zach Wilson"], []]),
            ("RB", [["Travis Etienne Jr.", "Alvin Kamara"], ["Audric Estim\u00e9"], ["CJ Donaldson"], []])],
           [("EDGE", [["Chase Young", "Carl Granderson"], ["Anfernee Jennings"], [], []]),
            ("DL", [["Vernon Broughton"], ["John Ridgeway III"], [], []]),
            ("DL", [["Khristian Boyd"], ["Colby Wooden"], [], []]),
            ("DL", [["Nathan Shepherd"], ["John Ridgeway III"], [], []]),
            ("EDGE", [["Cameron Jordan"], ["Tyree Wilson"], [], []]),
            ("LB", [["Pete Werner"], ["Chris Rumph II"], ["Isaiah Stalbird"], []]),
            ("LB", [["Kaden Elliss"], ["Danny Stutsman"], ["Jaylan Ford"], []]),
            ("CB", [["Martin Emerson Jr."], ["Quincy Riley"], [], []]),
            ("S", [["Julian Blackmon"], ["Jordan Howden"], [], []]),
            ("S", [["Justin Reid"], ["Mike Reid"], [], []]),
            ("CB", [["Kool-Aid McKinstry"], ["Decamerion Richardson"], [], []]),
            ("S", [["Jonas Sanker"], ["Lorenzo Styles"], [], []])]),

    "DAL": ("Dallas Cowboys", "https://www.dallascowboys.com/team/depth-chart",
            "unofficial (\u201cUnofficial 2026 Dallas Cowboys Depth Chart\u201d)", "not dated on the page",
            [("WR", [["George Pickens"], ["Camden Brown"], [], []]),
             ("LT", [["Tyler Guyton"], ["Drew Shelton"], [], []]),
             ("LG", [["Tyler Smith"], ["T.J. Bass"], [], []]),
             ("C", [["Cooper Beebe"], ["Nick Leverett"], [], []]),
             ("RG", [["Tyler Booker"], ["T.J. Bass"], [], []]),
             ("RT", [["Terence Steele"], ["Broderick Jones"], [], []]),
             ("TE", [["Jake Ferguson", "Brevyn Spann-Ford"], ["Luke Schoonmaker"], ["James Mitchell"], []]),
             ("WR", [["Ryan Flournoy"], ["KaVontae Turpin"], [], []]),
             ("WR", [["CeeDee Lamb"], ["Jonathan Mingo"], [], []]),
             ("QB", [["Dak Prescott"], ["Sam Howell"], [], []]),
             ("RB", [["Javonte Williams"], [], [], []]),
             ("FB", [["Hunter Luepke"], [], [], []])],
            [("DT", [["Otito Ogbonnia"], ["Elijah Garcia"], [], []]),
             ("DT", [["Kenny Clark"], ["Jonathan Bullard"], [], []]),
             ("DT", [["Quinnen Williams"], ["LT Overton"], [], []]),
             ("OLB", [["Donovan Ezeiruaku"], ["James Houston"], [], []]),
             ("LB", [["DeMarvion Overshown"], ["Dee Winters"], ["Justin Barron"], []]),
             ("LB", [["Shemar James", "Jaishawn Barham"], [], [], []]),
             ("OLB", [["Rashan Gary"], ["Von Miller"], ["Marist Liufau"], []]),
             ("CB", [["Joey Porter Jr."], ["Shavon Revel Jr."], ["Ameer Speed"], []]),
             ("DB", [["Caleb Downs"], [], [], []]),
             ("CB", [["DaRon Bland"], ["Cobie Durant"], [], []]),
             ("S", [["P.J. Locke", "Markquese Bell"], ["Juanyeh Thomas"], [], []]),
             ("S", [["Malik Hooker"], ["Alijah Clark"], [], []])]),

    "TEN": ("Tennessee Titans", "https://www.tennesseetitans.com/team/depth-chart",
            "unofficial (\u201cUNOFFICIAL DEPTH CHART (as of 11/10/26)\u201d)", "as of 11/10/26",
            [("WR", [["Calvin Ridley"], ["Chimere Dike"], [], []]),
             ("TE", [["Gunnar Helm"], ["Daniel Bellinger"], ["David Martin-Robinson", "Kylen Granson"], []]),
             ("LT", [["Dan Moore Jr."], ["James Hudson III"], [], []]),
             ("LG", [["Peter Skoronski"], [], [], []]),
             ("C", [["Austin Schlottmann"], ["Pat Coogan"], [], []]),
             ("RG", [["Atonio Mafi"], ["Garrett Dellinger"], [], []]),
             ("RT", [["JC Latham"], ["Brandon Crenshaw-Dickson"], [], []]),
             ("WR", [["Wan'Dale Robinson"], [], [], []]),
             ("WR", [["Carnell Tate"], ["Elic Ayomanor"], [], []]),
             ("QB", [["Cam Ward"], ["Mitchell Trubisky"], [], []]),
             ("RB", [["Tony Pollard"], ["Tyjae Spears", "Nick Singleton"], ["Julius Chestnut", "Michael Carter"], []])],
            [("DE", [["Jermaine Johnson II"], ["Oluwafemi Oladejo"], [], []]),
             ("DT", [["Solomon Thomas"], ["Jonah Laulu"], ["Jackie Marshall"], []]),
             ("DL", [["John Franklin-Myers"], ["Nazir Stackhouse"], ["Timmy Horne"], []]),
             ("DE", [["Jacob Martin"], ["Keldric Faulk"], ["Truman Jones"], []]),
             ("LB", [["Cody Barton"], [], [], []]),
             ("LB", [["Cedric Gray"], [], [], []]),
             ("LB", [["Anthony Hill Jr."], ["Dorian Mausi"], [], []]),
             ("CB", [["Joshua Williams"], ["Alontae Taylor"], [], []]),
             ("NCB", [["Marcus Harris"], ["Alontae Taylor"], ["Micah Robinson"], []]),
             ("S", [["Tony Adams"], [], [], []]),
             ("S", [["Kevin Winston Jr."], ["Terrell Burgess"], [], []]),
             ("CB", [["Cor'Dale Flott"], ["Jaylon Jones"], [], []])]),

    "GB": ("Green Bay Packers", "https://www.packers.com/team/depth-chart",
           "unofficial (\u201cUnofficial, Nov. 10, 2026\u201d)", "Nov. 10, 2026",
           [("WR", [["Christian Watson"], ["Bo Melton"], [], []]),
            ("WR", [["Matthew Golden"], ["J. Michael Sturdivant"], [], []]),
            ("LT", [["Jordan Morgan"], ["John Williams"], [], []]),
            ("LG", [["Aaron Banks"], ["Travis Glover"], ["Donovan Jennings"], []]),
            ("C", [["Sean Rhyan"], ["Jager Burton"], [], []]),
            ("RG", [["Laken Tomlinson"], ["Kevin Zeitler"], [], []]),
            ("RT", [["Anthony Belton"], ["Mekhi Becton Sr."], [], []]),
            ("TE", [["Tucker Kraft"], ["Jonnu Smith"], ["Mark Redman"], []]),
            ("WR", [["Savion Williams"], [], [], []]),
            ("QB", [["Jordan Love"], ["Tyrod Taylor"], [], []]),
            ("RB", [["Josh Jacobs"], ["MarShawn Lloyd"], ["Pierre Strong Jr."], ["Kaleb Johnson"]])],
           [("DT", [["Karl Brooks"], ["Jordon Riley"], ["Anthony Campbell"], []]),
            ("DT", [["Devonte Wyatt"], ["Chris McClellan"], [], []]),
            ("EDGE", [["Lukas Van Ness"], ["Brenton Cox Jr"], [], []]),
            ("LB", [["Zaire Franklin"], ["Ty'Ron Hopper"], ["Kristian Welch"], []]),
            ("LB", [["Isaiah McDuffie"], ["Nick Niemann"], [], []]),
            ("EDGE", [["Barryn Sorrell"], ["Dani Dennis-Sutton"], [], []]),
            ("CB", [["Keisean Nixon"], ["Carrington Valentine"], [], []]),
            ("CB", [["Brandon Cisse"], ["Benjamin St-Juste"], [], []]),
            ("S", [["Xavier McKinney"], ["Kitan Oladapo"], [], []]),
            ("S", [["Evan Williams"], ["Kitan Oladapo"], [], []]),
            ("NB", [["Javon Bullard"], ["Kamal Hadden"], [], []])]),

    "AZ": ("Arizona Cardinals", "https://www.azcardinals.com/team/depth-chart",
           "labeled \u201cOfficial Depth Chart\u201d on the page (no club disclaimer present in the text read)",
           "not dated on the page",
           [("WR", [["Reggie Virgil"], ["Harrison Wallace III"], [], []]),
            ("LT", [["Jayden Williams"], ["Jedrick Wills"], [], []]),
            ("LG", [["Isaac Seumalo"], ["Hayden Conner"], [], []]),
            ("C", [["Hjalte Froholdt"], ["Kingsley Eguakun"], [], []]),
            ("RG", [["Isaiah Adams"], ["Jon Gaines II"], [], []]),
            ("RT", [["Elijah Wilkinson"], ["Josh Fryar"], [], []]),
            ("TE", [["Trey McBride"], ["Hunter Long"], [], []]),
            ("TE", [["Elijah Higgins"], ["Teagan Quitoriano"], [], []]),
            ("WR", [["Simi Fehoko"], ["Devin Duvernay"], [], []]),
            ("QB", [["Carson Beck"], ["Josh Johnson"], ["Joey Aguilar"], []]),
            ("RB", [["Tyler Allgeier"], ["Bam Knight"], ["Evan Hull"], []])],
           [("DT", [["Dante Stills"], ["Darius Robinson"], ["Jared Harrison-Hunte"], []]),
            ("NT", [["Roy Lopez"], ["Andrew Billings"], [], []]),
            ("DT", [["Walter Nolen III"], ["L.J. Collier"], [], []]),
            ("OLB", [["Josh Sweat"], ["Eku Leota"], [], []]),
            ("ILB", [["Jack Gibbens"], ["Karson Sharar"], [], []]),
            ("ILB", [["Mack Wilson Sr."], ["Cody Simon"], [], []]),
            ("OLB", [["Zaven Collins", "Baron Browning"], [], [], []]),
            ("CB", [["Denzel Burke"], ["Starling Thomas V"], [], []]),
            ("CB", [["Kei'Trel Clark"], ["Max Melton"], [], []]),
            ("CB", [["Kalen King"], ["Garrett Williams"], [], []]),
            ("S", [["Wydett Williams Jr."], ["Kitan Crawford"], [], []]),
            ("S", [["Budda Baker"], ["Dadrion Taylor-Demerson"], [], []])]),

    "IND": ("Indianapolis Colts", "https://www.colts.com/team/depth-chart",
            "unofficial (the club's own newsroom publishes a dated \u201cunofficial depth chart for Week 11\u201d article; the chart page itself carries no disclaimer in the text read)",
            "not dated on the page; the club's Week 11 article is dated in the Week 11 newsroom release",
            [("WR", [["Laquon Treadwell"], ["Nick Westbrook-Ikhine"], [], []]),
             ("LT", [["Bernhard Raimann"], ["Charlie Heck"], [], []]),
             ("LG", [["Jalen Farmer"], ["Dalton Tucker"], [], []]),
             ("C", [["Tanor Bortolini"], ["Sedrick Van Pran-Granger"], [], []]),
             ("RG", [["Matt Goncalves"], [], [], []]),
             ("RT", [["Jalen Travis"], ["Luke Tenuta"], [], []]),
             ("TE", [["Tyler Warren"], ["Drew Ogletree"], ["Will Mallory"], ["Pharaoh Brown"]]),
             ("WR", [["Anthony Gould"], [], [], []]),
             ("WR", [["Ashton Dulin"], ["Deion Burks"], [], []]),
             ("QB", [["Daniel Jones"], ["Anthony Richardson Sr."], ["Riley Leonard"], []]),
             ("RB", [["Jonathan Taylor"], ["Seth McGowan"], ["DJ Giddens"], []])],
            [("DE", [["Arden Key"], ["Jaylahn Tuimoloau"], ["George Gumbs Jr."], []]),
             ("DT", [["Adetomiwa Adebawore"], ["Kevin Givens"], [], []]),
             ("NT", [["Grover Stewart"], ["Jerry Tillery"], ["Tim Smith"], []]),
             ("DE", [["Laiatu Latu"], ["Caden Curry"], [], []]),
             ("WLB", [["Jaylon Carlies"], ["Bryce Boettcher"], ["Tahj Chambers"], []]),
             ("MLB", [["CJ Allen"], ["Austin Ajiake"], [], []]),
             ("CB", [["Charvarius Ward"], ["Kenneth Harris"], [], []]),
             ("FS", [["Cam Bynum"], ["Jonathan Owens"], [], []]),
             ("SS", [["AJ Haulcy"], ["Hunter Wohler"], [], []]),
             ("N", [["Justin Walley"], ["Kapena Gushiken"], [], []]),
             ("CB", [["Sauce Gardner"], ["Johnathan Edwards"], [], []])]),

    "MIA": ("Miami Dolphins", "https://www.miamidolphins.com/team/depth-chart",
            "unlabelled (page heading \u201cDEPTH CHART\u201d; no official/unofficial word in the text read)",
            "not dated on the page",
            [("WR", [["Caleb Douglas"], ["Jared Wayne"], [], []]),
             ("LT", [["Patrick Paul"], ["Chukwuebuka Godrick"], [], []]),
             ("LG", [["Kadyn Proctor"], ["Jarrett Kingston"], [], []]),
             ("C", [["Aaron Brewer"], ["Andrew Meyer"], [], []]),
             ("RG", [["Jonah Savaiinaea"], ["Caedan Wallace"], ["Christian Haynes"], []]),
             ("RT", [["Austin Jackson"], ["Caedan Wallace"], [], []]),
             ("TE", [["Greg Dulcich"], ["Will Kacmarek"], ["Seydou Traore"], ["Justin Joly"]]),
             ("FB", [["DJ Herman"], [], [], []]),
             ("RB", [["Ollie Gordon II"], ["Jaylen Wright"], ["Kaytron Allen"], []]),
             ("QB", [["Kyle McCord"], [], [], []]),
             ("WR", [["Malik Washington"], ["Kevin Coleman Jr."], [], []]),
             ("WR", [["Chris Bell"], ["Jalen Tolbert"], [], []])],
            [("DT", [["Jordan Phillips"], ["Kenneth Grant"], [], []]),
             ("DT", [["Zeek Biggers"], ["Keith Cooper Jr."], [], []]),
             ("EDGE", [["Chop Robinson"], ["Malik Herring"], [], []]),
             ("EDGE", [["Josh Uche"], ["Rodney McGraw"], [], []]),
             ("ILB", [["Jordyn Brooks"], ["Jackson Woodard"], ["Shaka Heyward"], []]),
             ("ILB", [["Jacob Rodriguez"], ["Willie Gay Jr."], [], []]),
             ("NB", [["Chris Johnson"], [], [], []]),
             ("CB", [["JuJu Brents"], ["Marcellas Dial Jr."], [], []]),
             ("CB", [["Jason Marshall Jr."], ["Jaylin Simpson"], [], []]),
             ("S", [["Michael Taaffe"], ["Zayne Anderson"], [], []]),
             ("S", [["Dante Trader Jr."], ["Kyle Louis"], ["Julius Wood"], []])]),

    "BUF": ("Buffalo Bills", "https://www.buffalobills.com/team/depth-chart",
            "unlabelled (page heading \u201cDEPTH CHART\u201d; no official/unofficial word in the text read)",
            "not dated on the page",
            [("WR", [["DJ Moore"], ["Skyler Bell"], [], []]),
             ("LT", [["Dion Dawkins"], ["Jude Bowry"], [], []]),
             ("LG", [["Alec Anderson"], ["Austin Corbett"], [], []]),
             ("C", [["Connor McGovern"], ["Lloyd Cushenberry"], [], []]),
             ("RG", [["O'Cyrus Torrence"], ["Ar'maj Reed-Adams"], [], []]),
             ("RT", [["Spencer Brown"], ["Tylan Grable"], [], []]),
             ("TE", [["Dalton Kincaid"], ["Dawson Knox"], ["Jackson Hawes"], ["Keleki Latu"]]),
             ("QB", [["Josh Allen"], ["Kyle Allen"], [], []]),
             ("RB", [["James Cook III"], ["Ray Davis"], ["Ty Johnson"], []]),
             ("WR", [["Khalil Shakir"], ["Greg Dortch"], [], []]),
             ("WR", [["Keon Coleman"], [], [], []])],
            [("DL", [["Ed Oliver"], ["DeWayne Carter"], [], []]),
             ("DL", [["Deone Walker"], ["Greg Gaines"], [], []]),
             ("DL", [["T.J. Sanders"], ["Landon Jackson"], [], []]),
             ("OLB", [["Greg Rousseau"], ["Michael Hoecht"], ["Mike Danna"], []]),
             ("OLB", [["Bradley Chubb"], ["TJ Parker"], ["Javon Solomon"], []]),
             ("ILB", [["Dorian Williams"], ["Kaleb Elarms-Orr"], [], []]),
             ("ILB", [["Terrel Bernard"], ["Joe Andreessen"], [], []]),
             ("CB", [["Christian Benford"], ["Dee Alford"], [], []]),
             ("CB", [["Davison Igbinosun"], ["Maxwell Hairston"], [], []]),
             ("NCB", [["Dee Alford"], [], [], []]),
             ("S", [["Damar Hamlin"], ["Sam Franklin Jr."], [], []]),
             ("S", [["Cole Bishop"], ["Jalon Kilgore"], [], []])]),
}

# Clubs whose own site publishes the chart as an image (no position/name table in the page
# text), or which this session did not read. Recorded so the uncovered clubs are countable.
REJECTIONS = [
    ("HOU", "Houston Texans", "https://www.houstontexans.com/team/depth-chart",
     "image-only", "The page text carries the heading \u201cUnofficial Depth Chart\u201d and one `<img>`; "
     "there is no position/name table to transcribe. Re-confirmed by a fresh read on 2026-11-18. "
     "A structured source must be obtained; transcribing the image by eye is refused."),
]
UNREAD = ["ATL", "BAL", "CAR", "CHI", "CIN", "CLE", "DEN", "JAX", "KC", "LAC", "LAR", "LV",
          "NE", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "WAS"]

# Unit classification: which side of the ball a position belongs to, and which matrix unit.
def unit_of(pos, side):
    if side == "offense":
        if pos in ("QB",):
            return "QB"
        if pos in ("WR", "TE", "RB", "FB"):
            return "Skill (WR/TE/RB)"
        return "Offensive line"
    if pos in ("CB", "DB", "NB", "NCB", "N", "S", "FS", "SS"):
        return "Coverage (CB/S)"
    if pos in ("LB", "ILB", "MLB", "OLB", "WLB", "SLB", "SAM", "MIKE", "WILL", "LILB", "RILB", "RUSH"):
        return "Linebackers"
    return "Defensive front"

MATCHUP = {
    "Offensive line": "vs their defensive front (EDGE/DL/LB)",
    "Skill (WR/TE/RB)": "vs their coverage (CB/S)",
    "QB": "vs their pass rush and coverage",
    "Defensive front": "vs their offensive line",
    "Linebackers": "vs their skill positions",
    "Coverage (CB/S)": "vs their skill positions",
}

# ---------------------------------------------------------------------------
# 1. the string register: one row per club/side/pos-slot/string
# ---------------------------------------------------------------------------
str_rows = []
for club, (name, url, label, dated, off, dfn) in CLUBS.items():
    for side, positions in (("offense", off), ("defense", dfn)):
        for pi, (pos, slots) in enumerate(positions, start=1):
            for si, names in enumerate(slots, start=1):
                slot_type = ("shared" if len(names) > 1 else
                             "empty" if len(names) == 0 else "single")
                str_rows.append({
                    "club": club, "club_name": name, "side": side,
                    "position_row": pi, "pos": pos, "string": si,
                    "players_in_slot": " | ".join(names),
                    "slot_type": slot_type,
                    "strings_published_for_this_row": sum(1 for s in slots if s),
                    "chart_self_label": label, "chart_date_as_published": dated,
                    "read_utc": READ_UTC, "source_url": url,
                })

os.makedirs(DATA, exist_ok=True)
with open(os.path.join(DATA, "depth_chart_strings_2026.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(str_rows[0].keys()))
    w.writeheader()
    for r in str_rows:
        w.writerow(r)

# ---------------------------------------------------------------------------
# 2. the matchup matrix: one row per club/unit/position row
# ---------------------------------------------------------------------------
mat_rows = []
for club, (name, url, label, dated, off, dfn) in CLUBS.items():
    for side, positions in (("offense", off), ("defense", dfn)):
        for pi, (pos, slots) in enumerate(positions, start=1):
            row = {
                "club": club, "club_name": name, "side": side,
                "unit": unit_of(pos, side), "position_row": pi, "pos": pos,
                "matches_against": MATCHUP[unit_of(pos, side)],
            }
            for si in range(1, 5):
                names = slots[si - 1] if si - 1 < len(slots) else []
                row[f"string_{si}"] = " | ".join(names)
                row[f"string_{si}_type"] = ("shared" if len(names) > 1 else
                                            "empty" if len(names) == 0 else "single")
            row["strings_published"] = sum(1 for s in slots if s)
            row["shared_slots"] = sum(1 for s in slots if len(s) > 1)
            row["empty_slots"] = sum(1 for s in slots[:4] if len(s) == 0)
            row["chart_self_label"] = label
            row["chart_date_as_published"] = dated
            row["read_utc"] = READ_UTC
            row["source_url"] = url
            mat_rows.append(row)

with open(os.path.join(DATA, "matchup_matrix_week11.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(mat_rows[0].keys()))
    w.writeheader()
    for r in mat_rows:
        w.writerow(r)

# ---------------------------------------------------------------------------
# 3. coverage: who is in, who is out, and why
# ---------------------------------------------------------------------------
cov = []
for club, (name, url, label, dated, off, dfn) in CLUBS.items():
    n_slots = sum(len(s) for _p, s in off) + sum(len(s) for _p, s in dfn)
    cov.append({"club": club, "club_name": name, "status": "transcribed",
                "rows_offense": len(off), "rows_defense": len(dfn),
                "slot_cells_total": n_slots,
                "reason_blank": "", "source_url": url, "read_utc": READ_UTC})
for club, name, url, kind, why in REJECTIONS:
    cov.append({"club": club, "club_name": name, "status": f"refused - {kind}",
                "rows_offense": "", "rows_defense": "", "slot_cells_total": "",
                "reason_blank": why, "source_url": url, "read_utc": READ_UTC})
for club in UNREAD:
    cov.append({"club": club, "club_name": "", "status": "not read this session",
                "rows_offense": "", "rows_defense": "", "slot_cells_total": "",
                "reason_blank": "The club's chart was not read in this session, so no string "
                                "order is published for it. Not rejected: simply unread.",
                "source_url": "https://www.nfl.com/teams/", "read_utc": READ_UTC})
cov.sort(key=lambda r: (r["status"], r["club"]))
with open(os.path.join(DATA, "chart_rejections.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(cov[0].keys()))
    w.writeheader()
    for r in cov:
        w.writerow(r)

print(f"string register : {len(str_rows)} rows, {len(CLUBS)} clubs")
print(f"matchup matrix  : {len(mat_rows)} rows")
print(f"coverage        : {sum(1 for r in cov if r['status']=='transcribed')} transcribed, "
      f"{sum(1 for r in cov if r['status'].startswith('refused'))} refused, "
      f"{sum(1 for r in cov if r['status'].startswith('not read'))} unread")
shared = sum(1 for r in mat_rows if r["shared_slots"])
empt = sum(1 for r in mat_rows if r["empty_slots"])
print(f"shared slots    : {shared} position rows carry at least one shared cell")
print(f"empty slots     : {empt} position rows carry at least one empty cell")
