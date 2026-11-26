# Seven Sleepers v2: scene manifest and repair plan (25 Nov 2026)

Film: output/doc-did-seven-sleepers-hide-in-a-cave-and-awaken-/video.mp4, sha256 d885501e6a77deac0b019974d0f96f577ab6ceba88810cfac37b2dfb4bbda597 (backup: output_old/doc-did-seven-sleepers-v2-d885501e-before-repair-25nov).
Built by data/rescript/ss_scene_map.py (actual file per scene, by matching three frames of every scene against every candidate file) and data/rescript/ss_scene_manifest.py (judgements). Judgements are Claude's from frames and source titles: an assessment for a second reviewer and the owner, not a verdict. Machine-readable copy: data/rescript/scene_map_v2/scene_manifest_v2.json (full narration, prompts, files, licences).

## Summary

```
{
 "scenes": 109,
 "classification": {
  "REUSE_WITH_JUSTIFICATION": 7,
  "KEEP": 44,
  "REPLACE": 46,
  "NEEDS_HUMAN_REVIEW": 3,
  "REDRAW": 4,
  "REMOVE_TEXT": 5
 },
 "moves_of_existing_verified_files": [
  3,
  17,
  23,
  32,
  33,
  34,
  37,
  38,
  61,
  63,
  65,
  66,
  68
 ],
 "new_drawings_needed_at_most": 42,
 "scenes_needing_new_drawing": [
  5,
  6,
  7,
  12,
  14,
  16,
  18,
  19,
  20,
  21,
  22,
  24,
  25,
  26,
  27,
  28,
  30,
  36,
  39,
  40,
  41,
  42,
  43,
  45,
  46,
  51,
  53,
  55,
  56,
  60,
  67,
  69,
  73,
  81,
  87,
  91,
  92,
  98,
  104,
  105,
  106,
  107
 ],
 "scenes_where_a_verified_archive_picture_is_tried_first": [
  5,
  7,
  15,
  16,
  19,
  26,
  31,
  43,
  87
 ],
 "human_review": [
  31,
  50,
  65
 ]
}
```

## Scenes

| # | time | context | intended visual | actual picture | writing | dup | class | correction | conf |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0:00.1 | Opening (both traditions named) | sealed cave entrance | "The Seven Sleepers of Ephesus Discovered by Alexander the G (archive) | authentic (Persian captions in the painting) | - | REUSE_WITH_JUSTIFICATION | keep: an Islamic (Falnama) painting of the sleepers under a neutral opening question that names both traditions | high |
| 1 | 0:06.7 | Opening (both traditions named) | ancient manuscripts and cave | ASHAB-I KEHF MAGARASI - SEVEN SLEEPERS CAVE MERSIN TARSUS.jp (archive) | authentic sign | - | KEEP | keep: real photo of the claimed cave at Tarsus | high |
| 2 | 0:17.2 | Christian legend | Roman emperor Decius | Sept Dormants.jpg (archive) | authentic | - | KEEP | keep | high |
| 3 | 0:30.5 | Christian legend | youths praying in cave | Berlin, Pertsch Persisch 1016 fol 187r Seven Sleepers.jpg (archive) | authentic Persian script | - | REPLACE | MOVE the Russian icon now at scene 7 here (Christian icon for the Christian legend); MOVE this Persian miniature to scene 37 | high |
| 4 | 0:41.9 | Christian legend | stones sealing a cave | Greek Fresco of the Seven Sleepers of Ephesos.jpg (archive) | authentic (Greek) | - | KEEP | keep | high |
| 5 | 0:51.1 | Roman history: the Decian edict of AD 250 | Roman emperor making an offering at an altar on a winter morning | Russian Icon of the Seven Sleepers of Ephesos.jpg (archive) | authentic | - | REPLACE | draw: a Roman emperor offering at an altar, no writing (or a verified CC0 museum portrait/coin of Trajan Decius) | high |
| 6 | 1:05.3 | Roman history: the Decian edict of AD 250 | Roman magistrate watching a citizen burn incense at a small altar | Russian Icon of the Seven Sleepers of Ephesos with Vine Fram (archive) | authentic | - | REPLACE | draw: a Roman magistrate watching a citizen burn incense, no writing | high |
| 7 | 1:18.2 | Roman history: the Decian edict of AD 250 | rolled papyrus scrolls tied with cord in a clay jar | Russian Icon of the Seven Sleepers with Christ Emmanuel.jpg (archive) | authentic | - | REPLACE | a verified photo of a surviving Decian libellus papyrus (public-domain/CC museum record) if found; otherwise draw rolled papyri with NO writing | high |
| 8 | 1:29.9 | Roman history: the Decian edict of AD 250 | early Christians gathered in a dark rock-cut chamber by oil lamp | Russian Icon of the Seven Sleepers with the Mandylion.jpg (archive) | authentic | - | REUSE_WITH_JUSTIFICATION | keep: Christian icon of the youths under 'a choice between their faith and the decree' | medium |
| 9 | 1:41.7 | Roman history: the Decian edict of AD 250 | empty Roman street at dusk with shuttered houses | Seven Sleepers icon.jpeg (archive) | authentic | - | REUSE_WITH_JUSTIFICATION | keep: icon of the hidden youths under 'many others went into hiding' | medium |
| 10 | 1:53.7 | Christian legend | Roman empire map | Roman Empire Map (archive) | authentic map labels | - | KEEP | keep | high |
| 11 | 2:07.5 | Christian legend | Byzantine church council | Theodosius Arrives at Ephesus, from a Scene from the Legend  (archive) | none | - | KEEP | keep | high |
| 12 | 2:19.4 | Christian legend | landowner at cave mouth | St. Paul Dictating at Ephesus (archive) | none | - | REPLACE | draw: a landowner and workers opening a sealed cave mouth, cattle nearby, no writing | high |
| 13 | 2:28.7 | Christian legend | young man walking to city | Blender globe (blender) | place label | - | KEEP | keep: Blender globe to Ephesus | high |
| 14 | 2:37.9 | Christian legend | ancient city with crosses | A figure supporting a tablet with a representation of a herm (archive) | none | - | REPLACE | draw: a late-Roman city street with church crosses on the buildings, no writing | high |
| 15 | 2:47.5 | Christian legend | old Roman coins | Old Roman coin, closeup (archive) | none legible | - | REPLACE | a verified CC0 museum photo of a coin of Trajan Decius (real legend on the coin); never an AI coin (it would carry invented letters) | high |
| 16 | 2:56.8 | Christian legend | bishop in old church | Drachm of Ephesus, 330 B.C., from the Ancient Coins series ( (archive) | printed museum label | - | REPLACE | draw: a bishop in an old church listening to the youths, no writing; or a verified panel of the same Met stained-glass legend series if one shows this | high |
| 17 | 3:06.7 | Syriac Christian sources and modern scholarship | Syriac bishop writing | Tetradrachm Coin of Erognetos, Magistrate of Magnesia (archive) | Greek coin legend | 18,19,45 | REPLACE | MOVE the Syriac depiction of Jacob of Serugh now at scene 36 here (it names him) | high |
| 18 | 3:20.1 | Syriac Christian sources and modern scholarship | lost Greek scroll | Tetradrachm Coin of Herognetos, Magistrate of Magnesia (archive) | Greek coin legend | 17,19 | REPLACE | draw: a sealed, rolled scroll in shadow, NO writing | high |
| 19 | 3:31.6 | Syriac Christian sources and modern scholarship | old Syriac manuscript | Tetradrachm Coin of Herognetos, Magistrate of Magnesia (archive) | Greek coin legend | 17,18,45 | REPLACE | a verified image of an early Syriac manuscript of the legend if found with its library record; otherwise draw a closed old codex, NO visible writing | high |
| 20 | 3:45.7 | Syriac Christian sources and modern scholarship | manuscript in museum | Cave of the seven sleepers 1 Amman Jordan.jpg (archive) | none | - | REPLACE | draw: an old codex in a museum case, NO visible writing; MOVE this Amman photo out (not needed: unused) | high |
| 21 | 3:59.5 | Syriac Christian sources and modern scholarship | Byzantine scholar writing | Cave of the seven sleepers 2 Amman Jordan.jpg (archive) | none | - | REPLACE | draw: a Byzantine scholar writing, page not visible, NO writing; this doorway photo MOVES to scene 66 | high |
| 22 | 4:12.7 | Syriac Christian sources and modern scholarship | pilgrims walking to Ephesus | Cave of the seven sleepers 3 Amman Jordan.jpg (archive) | none | - | REPLACE | draw: pilgrims on the road to Ephesus at dawn, no writing; this door photo MOVES to scene 63 | high |
| 23 | 4:25.0 | Latin Christian West, 6th-13th century | Gregory of Tours | (Castres) Retable de saint Martin - La Messe de saint Grégoi (archive) | authentic | - | REPLACE | MOVE the Gregory of Tours manuscript now at scene 41 here, described as a page of his own miracle writings (on St Martin), not the sleepers chapter | high |
| 24 | 4:38.3 | Latin Christian West, 6th-13th century | medieval scribe listening | Cave of the seven sleepers 4 Amman Jordan.jpg (archive) | none | - | REPLACE | draw: a medieval scribe listening to a traveller, page not visible, NO writing | high |
| 25 | 4:49.2 | Latin Christian West, 6th-13th century | medieval monk writing | Cave of the seven sleepers Amman Jordan.jpg (archive) | none | - | REPLACE | draw: a monk writing at a desk in an 8th-century scriptorium, page not visible, NO writing | high |
| 26 | 5:00.4 | Latin Christian West, 6th-13th century | Golden Legend book | Seven Sleepers (أصحاب الكهف).jpg (archive) | none | - | REPLACE | a verified public-domain miniature of the Seven Sleepers from a Golden Legend manuscript or early print if found; otherwise draw a closed medieval boo | high |
| 27 | 5:14.8 | Latin Christian West, 6th-13th century | shelves of manuscripts | The Cave of the Seven Sleepers in Amman, Jordan, April 21, 2 (archive) | none | - | REPLACE | draw: shelves of medieval manuscripts in a library, spines plain, NO writing | high |
| 28 | 5:25.2 | Latin Christian West, 6th-13th century | Irish monastery calendar | Islamic Manuscript, Tarjamat al-Sultani, Agha Muhammad al-Su (archive) | authentic Arabic script | - | REPLACE | draw: an Irish monastery at dawn (no calendar page shown), NO writing | high |
| 29 | 5:37.7 | Latin Christian West, 6th-13th century | map of medieval trade routes | Europe map 1092.PNG (archive) | authentic map labels | - | REUSE_WITH_JUSTIFICATION | keep: a map of Europe in 1092 under the spread of versions in many languages | medium |
| 30 | 5:54.5 | Crusades and church calendars | crusader ship at sea | Islamic Manuscript, Tarjamat al-Sultani, Agha Muhammad al-Su (archive) | authentic Persian script | - | REPLACE | draw: a crusader ship at sea, no writing | high |
| 31 | 6:07.0 | Crusades and church calendars | stone coffin in abbey | Stone Coffins (archive) | none | - | NEEDS_HUMAN_REVIEW | keep, or a verified photo of the Saint-Victor (Marseille) sarcophagi; the current photo is stone coffins of unknown place and may be taken for the cof | medium |
| 32 | 6:19.0 | Crusades and church calendars | Orthodox icon of seven youths | Surah Al-Kahf.png (archive) | authentic Arabic (correct) | - | REPLACE | MOVE the Russian icon now at scene 5 here (Orthodox icon of the Holy Seven Youths) | high |
| 33 | 6:30.7 | Crusades and church calendars | church calendar page | COLLECTIE TROPENMUSEUM Pagina uit een koran TMnr 687-61.jpg (archive) | authentic Arabic (Q 18:1-2 by Claude's reading) | - | REPLACE | MOVE the Russian icon now at scene 6 here (Orthodox commemoration under the calendars) | high |
| 34 | 6:42.4 | Qur'an and Islamic tradition | Quran manuscript Al-Kahf | King Abgar V, son of the Arameans.png (archive) | authentic Syriac | - | REPLACE | MOVE the 'Surah al-Kahf 18' roundel now at scene 32 here (correct title and number) | high |
| 35 | 6:54.7 | Qur'an and Islamic tradition | two riders crossing the desert toward an oasis town at dawn | Blender dunes (blender) | none | 46 | REUSE_WITH_JUSTIFICATION | keep: Blender dunes under Arabia (no people drawn) | medium |
| 36 | 7:08.8 | Qur'an and Islamic tradition | desert night sky over an oasis town | Ancient syriac manuscript jacob of serugh (archive) | authentic Syriac | - | REPLACE | draw: desert night sky over an oasis town, no writing; the Syriac picture MOVES to scene 17 | high |
| 37 | 7:22.5 | Qur'an and Islamic tradition | cave mouth at dusk | st jakob, st james, funes, vilnöss, south tyrol, südtirol, c (archive) | none | - | REPLACE | MOVE the Persian miniature now at scene 3 here (Islamic depiction of the Companions of the Cave) | high |
| 38 | 7:33.2 | Qur'an and Islamic tradition | Quran open at middle | pilgrim, sculptures, hohenberg, rosenberg, floor, characters (archive) | none | - | REPLACE | MOVE the Tropenmuseum Qur'an page now at scene 33 here, AFTER a second reader confirms it is Q 18:1-2 (else draw a closed book on a stand, no writing) | high |
| 39 | 7:46.4 | Qur'an and Islamic tradition | light inside cave | Chilpéric Ier et évêques.jpg (archive) | authentic French | - | REPLACE | draw: soft light inside a cave, no writing | high |
| 40 | 7:53.7 | Qur'an and Islamic tradition | Arabic calligraphy verse | Gregoryoftours.jpg (archive) | authentic Latin labels | - | REPLACE | draw: a lamp in a dark cave with a dog's silhouette at the entrance, NO writing (never imitate the verse) | high |
| 41 | 8:05.9 | Qur'an and Islamic tradition | lamp beside Quran | Grégoire de Tours-Vita sancti Martini.jpg (archive) | authentic Latin | - | REPLACE | draw: a lamp beside a closed book in a dark room, NO writing; the Latin manuscript MOVES to scene 23 | high |
| 42 | 8:16.1 | Qur'an and Islamic tradition | quiet courtyard of an old mosque at dawn | Saint Grégoire Sacramentaire de Marmoutier à l'usage d'Autun (archive) | none | 43 | REPLACE | draw: a quiet old mosque courtyard at dawn, plain walls, NO inscriptions | high |
| 43 | 8:25.5 | Qur'an and Islamic tradition | scholar reading tafsir | Saint Grégoire Sacramentaire de Marmoutier à l'usage d'Autun (archive) | none | 42 | REPLACE | draw: a scholar reading at a low desk, page not visible, NO writing (or a verified manuscript of Tafsir Ibn Kathir with its library record) | high |
| 44 | 8:38.2 | Qur'an and Islamic tradition | Najran in Arabia | Najran Fort, Saudi Arabia.jpg (archive) | none | - | REUSE_WITH_JUSTIFICATION | keep, described as Najran today: the fort is a 20th-century building, not 6th-century Najran | medium |
| 45 | 8:51.9 | Qur'an and Islamic tradition | dog guarding cave | Григорий Турский. Отрывок из книги И.В. Помяловского ... (Ru (archive) | authentic Russian print | 17,19 | REPLACE | draw: a dog lying at a cave entrance, NO writing | high |
| 46 | 9:02.7 | Qur'an and Christian chronologies | night sky over desert | Blender dunes (blender) | none | 35 | REPLACE | draw: a night sky over the desert (the note asks for it), no writing | medium |
| 47 | 9:14.2 | Qur'an and Christian chronologies | sun and moon | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 48 | 9:23.5 | Qur'an and Christian chronologies | hourglass on stone | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 49 | 9:40.8 | Qur'an and Christian chronologies | stack of old books | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 50 | 9:54.2 | Qur'an and Christian chronologies | medieval book open | AI drawing for this line (drawn) | faint, illegible | - | NEEDS_HUMAN_REVIEW | check at full size: faint illegible writing on the drawn book pages; redraw with NO writing if it reads as letters | low |
| 51 | 10:09.5 | Comparative: Jewish, Syriac, Latin, Catholic, Arabic lists | three figures in cave | Three Figures, from Cave 224 (archive) | none | - | REPLACE | draw: three youths and a dog asleep in a cave, no writing | high |
| 52 | 10:20.8 | Comparative: Jewish, Syriac, Latin, Catholic, Arabic lists | watcher at cave entrance | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 53 | 10:35.1 | Comparative: Jewish, Syriac, Latin, Catholic, Arabic lists | list of names on parchment | AI drawing for this line (drawn) | fake (pseudo-Latin) | - | REDRAW | draw: a rolled parchment tied with cord, NO writing | high |
| 54 | 10:49.2 | Comparative: Jewish, Syriac, Latin, Catholic, Arabic lists | two churches side by side | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 55 | 11:04.1 | Comparative: Jewish, Syriac, Latin, Catholic, Arabic lists | Arabic manuscript of names | Illuminated Manuscript Koran, Titlepiecewith a bequest (waqf (archive) | authentic Arabic | - | REPLACE | draw: an Arab scholar writing by lamplight, page not visible, NO writing | high |
| 56 | 11:14.5 | Comparative: Jewish, Syriac, Latin, Catholic, Arabic lists | mountain cave entrance | Carlsbad Caverns Natural Entrance (archive) | none | - | REPLACE | draw: a mountain cave entrance at dusk, no writing | medium |
| 57 | 11:25.1 | Archaeology: Ephesus | ruins of Ephesus | Ephesus Ruins of the Temple of Diana Eph.jpg (archive) | none | - | REUSE_WITH_JUSTIFICATION | keep: an engraving of the ruins of Ephesus under 'the earliest claim (Ephesus)' | medium |
| 58 | 11:35.2 | Archaeology: Ephesus | Mount Pion slope | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 59 | 11:46.1 | Archaeology: Ephesus | archaeological excavation | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 60 | 11:56.9 | Archaeology: Ephesus | grotto wall with weathered carved burial niches by candlelight | AI drawing for this line (drawn) | fake (garbled, small) | - | REMOVE_TEXT | redraw with a note that names no inscription: candle-lit grotto with empty burial niches, NO writing | high |
| 61 | 12:08.5 | Archaeology and Islamic history: the cave near Amman | cave near Amman Jordan | AI drawing for this line (drawn) | none | - | REPLACE | MOVE the real 2011 photo of the Amman site (now at scene 27) here | medium |
| 62 | 12:19.8 | Archaeology and Islamic history: the cave near Amman | rocky hillside above a small village in Jordan at dusk | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 63 | 12:32.4 | Archaeology and Islamic history: the cave near Amman | old photograph of cave | AI drawing for this line (drawn) | none | - | REPLACE | MOVE the real Amman cave door photo (now at scene 22) here; the drawn 'old photograph' presents an invented artifact as the 1951 photo | high |
| 64 | 12:45.6 | Archaeology and Islamic history: the cave near Amman | 1950s journal photograph | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 65 | 12:54.9 | Archaeology and Islamic history: the cave near Amman | stone sarcophagi in cave | AI drawing for this line (drawn) | fake glyphs (small) | - | NEEDS_HUMAN_REVIEW | MOVE the real cave interior with a tomb niche (now at scene 26) here only if its Commons record places it at the Amman cave; else draw stone sarcophag | medium |
| 66 | 13:07.4 | Archaeology and Islamic history: the cave near Amman | cave entrance with pilasters | AI drawing for this line (drawn) | none | - | REPLACE | MOVE the real doorway with carved capitals (now at scene 21) here: it shows the pilasters the line describes | high |
| 67 | 13:21.3 | Archaeology and Islamic history: the cave near Amman | Byzantine cemetery | AI drawing for this line (drawn) | none | - | REPLACE | draw: a small ruined early mosque above a cave entrance, plain walls, NO inscriptions | high |
| 68 | 13:35.5 | Archaeology and Islamic history: the cave near Amman | Kufic inscription | AI drawing for this line (drawn) | FAKE ARABIC (presented as Qur'anic) | - | REPLACE | MOVE the real carved wall detail of the Amman cave (now at scene 24) here, described as the cave's wall, NOT as the Kufic inscription; never draw the  | high |
| 69 | 13:48.2 | Archaeology and Islamic history: the cave near Amman | mosque ruins at cave | AI drawing for this line (drawn) | none | - | REPLACE | draw: ruins of an early mosque at a cave mouth in morning light, no writing, no bones | high |
| 70 | 13:59.4 | Other claimed sites (Turkey, Syria, Damascus) | Turkish mountain landscape | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 71 | 14:10.8 | Other claimed sites (Turkey, Syria, Damascus) | marble niches | Blender temple (blender) | none seen at 480x270 | - | KEEP | keep | medium |
| 72 | 14:24.1 | Other claimed sites (Turkey, Syria, Damascus) | Seljuk mosque interior | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 73 | 14:32.9 | Other claimed sites (Turkey, Syria, Damascus) | mosque in Afşin | AI drawing for this line (drawn) | fake Arabic | - | REDRAW | draw: the interior of the Afşin mosque with arches, plain walls, NO inscriptions | high |
| 74 | 14:46.5 | Other claimed sites (Turkey, Syria, Damascus) | rock-cut monastery | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 75 | 14:58.5 | Other claimed sites (Turkey, Syria, Damascus) | Mount Qasioun above old Damascus at dusk | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 76 | 15:11.1 | Other claimed sites (Turkey, Syria, Damascus) | old Damascus bathhouse | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 77 | 15:19.4 | Other claimed sites (Turkey, Syria, Damascus) | map of Middle East | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 78 | 15:30.3 | Literature and modern reception | Tudor stage play | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 79 | 15:42.3 | Literature and modern reception | Romantic era writer | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 80 | 15:52.7 | Literature and modern reception | Rip van Winkle illustration | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 81 | 16:08.0 | Literature and modern reception | king asleep in mountain | AI drawing for this line (drawn) | fake glyphs (small) | - | REMOVE_TEXT | redraw with NO marks on the cave wall (low priority) | medium |
| 82 | 16:19.3 | Literature and modern reception | fantasy novel cover | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 83 | 16:31.0 | Literature and modern reception | terracotta dog in cave | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 84 | 16:43.6 | Literature and modern reception | 1980s rock album | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 85 | 16:59.8 | Literature and modern reception | person sleeping late | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 86 | 17:12.9 | Literature and modern reception | animal hibernating | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 87 | 17:22.9 | Literature and modern reception | television studio | AI drawing for this line (drawn) | fake map labels (small) | - | REPLACE | a verified, freely licensed photo of Farajollah Salahshoor (e.g. CC BY 4.0 on Commons) if one exists with its record; otherwise draw a 1990s televisio | high |
| 88 | 17:36.9 | German folklore and weather | German summer village | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 89 | 17:46.4 | German folklore and weather | medieval German church | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 90 | 17:55.0 | German folklore and weather | dormouse | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 91 | 18:04.1 | German folklore and weather | old calendar | AI drawing for this line (drawn) | fake (garbled numerals) | - | REMOVE_TEXT | redraw the calendar with no readable numbers (low priority) | medium |
| 92 | 18:16.4 | German folklore and weather | weather over Germany | Blender sea (blender) | none | 98 | REPLACE | draw: summer sky over a southern German village, no writing | high |
| 93 | 18:28.6 | German folklore and weather | weather map Europe | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 94 | 18:42.3 | German folklore and weather | jet stream over globe | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 95 | 18:51.2 | German folklore and weather | summer storm clouds | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 96 | 19:03.1 | Comparative: Greek and Jewish sleepers, folklore | starry night over a mountain cave | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 97 | 19:13.5 | Comparative: Greek and Jewish sleepers, folklore | young shepherd asleep in a Cretan mountain cave, sheep outside | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 98 | 19:27.3 | Comparative: Greek and Jewish sleepers, folklore | old Greek seer with a staff looking over the sea | Blender sea (blender) | none | 92 | REPLACE | draw: an old Greek seer with a staff looking over the sea (the note asks for him), no writing | high |
| 99 | 19:36.7 | Comparative: Greek and Jewish sleepers, folklore | old scholar walking on a dry road through stony hills | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 100 | 19:48.7 | Comparative: Greek and Jewish sleepers, folklore | man planting a young carob tree on a stony hillside | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 101 | 20:01.5 | Comparative: Greek and Jewish sleepers, folklore | old man beside a tall carob tree heavy with pods | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 102 | 20:13.6 | Comparative: Greek and Jewish sleepers, folklore | storyteller beside a fire, listeners in shadow | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 103 | 20:25.8 | Comparative: Greek and Jewish sleepers, folklore | sunrise over mountains seen from inside a cave | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
| 104 | 20:38.8 | Method and conclusion | old manuscript in candlelight | AI drawing for this line (drawn) | fake (pseudo-Latin) | - | REDRAW | draw: an old closed book by candlelight, NO writing | high |
| 105 | 20:49.3 | Method and conclusion | sarcophagus with bones | AI drawing for this line (drawn) | fake (small) | - | REMOVE_TEXT | redraw the sarcophagus with no letters (low priority) | medium |
| 106 | 21:01.1 | Method and conclusion | pilgrims at a shrine | AI drawing for this line (drawn) | fake (small) | - | REMOVE_TEXT | redraw with a plain lintel (low priority) | medium |
| 107 | 21:11.4 | Method and conclusion | two faiths' manuscripts | AI drawing for this line (drawn) | FAKE ARABIC | - | REDRAW | draw: two closed old books side by side, NO writing on covers or pages | high |
| 108 | 21:23.9 | Method and conclusion | cave at dawn | AI drawing for this line (drawn) | none seen at 480x270 | - | KEEP | keep | medium |
