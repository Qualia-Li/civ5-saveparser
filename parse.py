import FileReader as fr
import xml.etree.cElementTree as ET
import pickle

__author__ = "Hussein Kaddoura"
__copyright__ = "Copyright 2013, Hussein Kaddoura"
__credits__ = ["Hussein Kaddoura"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Hussein Kaddoura"
__email__ = "hussein.nawwaf@gmail.com"
__status__ = "Development"

traits = { 1:"alive",
           3: "human",
           2: "dead",
}

victories = { 1: "VICTORY_TIME",
              2: "VICTORY_SPACE_RACE",
              3: "VICTORY_DOMINATION",
              4: "VICTORY_CULTURAL",
              5: "VICTORY_DIPLOMATIC",
}

def parse(filename):
    """ Parses the save file and transforms it to xml    """
    root = ET.Element("root")

    with fr.FileReader(filename) as civ5Save:
        parse_base(civ5Save, root)
        parse_compressed_payload(civ5Save, root)

    tree = ET.ElementTree(root)
    tree.write(filename + '.transformed.xml')

def parse_base(fileReader, xml):
    """
        Parse the general game options
        Code is definitely not optimal. We'll go through a round a refactoring after mapping more information
        Refactoring 1: Remove all localization queries. This will be done on a later note.
    """

    base = ET.SubElement(xml, 'base')
    version = ET.SubElement(base , 'version')

    fileReader.skip_bytes(4) #always CIV5

    save_version = fileReader.read_int()
    print("Save version:", save_version)
    version.set('save', str(save_version))
    
    game_version = fileReader.read_string()
    print("Game version:", game_version)
    version.set('game', game_version)
    
    build_version = fileReader.read_string()
    print("Build version:", build_version)
    version.set('build', build_version)

    game = ET.SubElement(base, 'game')
    current_turn = fileReader.read_int()
    print("Current turn:", current_turn)
    game.set('currentturn', str(current_turn))

    fileReader.skip_bytes(1) #TODO: I'll investigate later as to what this byte hold

    civilization = ET.SubElement(base, 'civilization')
    civ_name = fileReader.read_string()
    print("Civilization:", civ_name)
    civilization.text = civ_name

    handicap = ET.SubElement(base, 'handicap')
    handicap_level = fileReader.read_string()
    print("Handicap:", handicap_level)
    handicap.text = handicap_level

    era = ET.SubElement(base, 'era')
    starting_era = fileReader.read_string()
    print("Starting era:", starting_era)
    era.set('starting', starting_era)
    current_era = fileReader.read_string()
    print("Current era:", current_era)
    era.set('current', current_era)

    gamespeed = ET.SubElement(base, 'gamespeed')
    game_speed = fileReader.read_string()
    print("Game speed:", game_speed)
    gamespeed.text = game_speed

    worldsize = ET.SubElement(base, 'worldsize')
    world_size = fileReader.read_string()
    print("World size:", world_size)
    worldsize.text = world_size

    mapscript = ET.SubElement(base, 'mapscript')
    map_script = fileReader.read_string()
    print("Map script:", map_script)
    mapscript.text = map_script

    fileReader.skip_bytes(4) #TODO: an int
    #
    dlcs = ET.SubElement(base, 'dlcs')

    
    while fileReader.peek_int() != 0:
        fileReader.skip_bytes(16) #TODO: some binary data
        fileReader.skip_bytes(4) #TODO: seems to be always 1
        dlc = ET.SubElement(dlcs, 'dlc')
        try:
            dlc_name = fileReader.read_string()
            print("DLC:", dlc_name)
            dlc.text = dlc_name
        except:
            print("Error reading DLC string")
            # print("Position:", fileReader.pos)
            # print("Next int:", fileReader.peek_int())
            # print("Attempted string:", fileReader.read_string())
    #
    # #Extract block position (separated by \x40\x00\x00\x00 (@) )
    # #I haven't decoded what each of these blocks mean but I'll extract their position for the time being.

    bit_block_position = tuple(fileReader.findall('0x40000000'))
    #32 blocks have been found. We'll try to map them one at a time.

    #block 1
    fileReader.pos = bit_block_position[0] + 32 #remove the delimiter (@)
    block1 = tuple(map(lambda x: x.read(32).intle, fileReader.read_bytes(152).cut(32)))

    #TODO: block2 - seems to only contain Player 1?

    #block3
    #contains the type of civilization - 03 human, 01 alive, 04 missing, 02 dead
    fileReader.pos = bit_block_position[2] + 32
    leader_traits = tuple(map(lambda x: x.read(32).intle, fileReader.read_bytes(256).cut(32)))
    print("\nLeader traits:", [traits.get(trait, f"Unknown({trait})") for trait in leader_traits])

    #TODO: block4
    #TODO: block5
    #TODO: block6

    #block 7
    # contains the list of civilizations
    civilizations = fileReader.read_strings_from_block(bit_block_position[6] + 32, bit_block_position[7])
    print("\nCivilizations:", civilizations)

    #block 8
    #contains the list of leaders
    leaders = fileReader.read_strings_from_block(bit_block_position[7] + 32, bit_block_position[8], True)
    print("Leaders:", leaders)

    #TODO: block9-18

    #block 19
    # contains the civ states. There seems to be a whole bunch of leading 0s.
    fileReader.forward_to_first_non_zero_byte(bit_block_position[18] + 32, bit_block_position[19])
    civStates = fileReader.read_strings_from_block(fileReader.pos, bit_block_position[19], True)
    print("\nCity-States:", civStates)

    #TODO: block 20 - there's a 16 byte long list of 01's
    #TODO: block 21 - seems to be FFs
    #TODO: block 22, 23 - 00s
    #TODO: block 24 - player colors
    #TODO: blocks 25-27

    #block 28
    #the last 5 bytes contain the enabled victory types
    fileReader.pos = bit_block_position[28] - 5*8
    victorytypes = (fileReader.read_byte(), fileReader.read_byte(), fileReader.read_byte(), fileReader.read_byte(), fileReader.read_byte())
    print("\nVictory types enabled:")
    for idx, enabled in enumerate(victorytypes, start=1):
        if idx in victories:
            print(f"- {victories[idx]}: {'Yes' if enabled else 'No'}")

    #block 29
    # have the game options
    fileReader.find(b'GAMEOPTION', bit_block_position[28]+32, bit_block_position[29])
    fileReader.pos -= 32
    gameoptions = []
    print("\nGame options:")
    while fileReader.pos < bit_block_position[29]:
        option = fileReader.read_string()
        if option == "":
            break
        state = fileReader.read_int()
        print(f"- {option}: {'Enabled' if state else 'Disabled'}")
        gameoptions.append((option, state))

    #TODO: block 30-31

    #TODO: block 32
    #contains the zlib compressed data

    civs = tuple(map(lambda civ, trait, leader:  (civ, trait, leader),civilizations,leader_traits, leaders))

    civsXml = ET.SubElement(base, 'civilizations')
    for civ in civs:
        if civ[1] != 4:
            civXml = ET.SubElement(civsXml, 'civilization')
            civXml.set('name', civ[0])
            civXml.set('trait', traits[civ[1]])
            civXml.set('leader', civ[2])

    civStatesXml = ET.SubElement(base, 'civStates')
    for civState in civStates:
        civStateXml = ET.SubElement(civStatesXml, 'civState')
        civStateXml.text = civState

    victoriesXml = ET.SubElement(base, 'victories')
    for idx, victory in enumerate(victorytypes, start=1):
        victoriesXml.set(victories[idx], str(victory))

    gameoptionsXml = ET.SubElement(base, 'gameoptions')
    for gameoption in gameoptions:
        gameoptionXml = ET.SubElement(gameoptionsXml, 'gameoption')
        gameoptionXml.set('enabled', str(gameoption[1]))
        gameoptionXml.text = gameoption[0]

def parse_compressed_payload(fileReader, xml):
    files = fileReader.extract_compressed_payloads()

    details = ET.SubElement(xml, 'details')
    with fr.FileReader(files[0]) as f:
        f.read_int() # 1?
        f.read_int() # 0?
        f.read_int() #current turn, already extracted in the main save file
        f.read_int() # 0
        f.read_int() # 0
        f.read_int() # -4000 : starting year?
        f.read_int() # 500  : max turn count?
        f.read_int() # 500 : max turn count?
        playedtime = f.read_int() # playing time in seconds + a last digit

        lastDigit = playedtime % 10
        totalSeconds = int((playedtime - lastDigit) / 10)

        hours, totalSeconds = divmod(totalSeconds , 3600)

        minutes, seconds = divmod(totalSeconds, 60)
        # seconds = (totalSeconds - hours * 3600 - minutes * 60)

        # print(hours, minutes, seconds)

        p = ET.SubElement(details,'timeplayed')
        p.set('hours', str(hours))
        p.set('minutes', str(minutes))
        p.set('seconds', str(seconds))
        p.set('last',str(lastDigit))

        f.read_int() # 0?

        # bunch of bytes. TODO: investigate
        f.skip_bytes(90)

        #comes a list of string stuff.TODO: what do they refer to?
        nb_notes  = f.read_int()
        ns = ET.SubElement(details, 'notes')
        for note in range(0, nb_notes):
            n = ET.SubElement(ns, "note")
            n.text = f.read_string()

        print("\nSkipping to next data section...")
        f.pos = f.find_first('0xC1F2439C016F26110F014A49D3CA01A564ABAD01')[0] + 20 * 8

        #skipping some 20 bytes long blocks
        nb = f.read_int()
        print(f"\nSkipping {nb} blocks of 24 bytes each...")
        for i in range(0,nb):
            f.skip_bytes(24)

        #get some city stuff notification
        nb_cities = f.read_int()
        print(f"\nReading {nb_cities} city notifications:")
        citiesXml = ET.SubElement(details, 'citynotes')
        for i in range(0,nb_cities):
            city_note = f.read_string()
            print(f"City note {i+1}: {city_note}")
            cityXml = ET.SubElement(citiesXml, 'note')
            cityXml.text = city_note

        #get some notes about great persons
        nb_great_persons = f.read_int()
        print(f"\nReading {nb_great_persons} great person notifications:")
        greatPersonsXml= ET.SubElement(details, 'gpnotes')
        for i in range(0, nb_great_persons):
            gp_note = f.read_string()
            print(f"Great Person note {i+1}: {gp_note}")
            gpXml = ET.SubElement(greatPersonsXml, 'note')
            gpXml.text = gp_note

        print("\nProcessing histogram data...")
        histograms = {}
        histogram_labels = {}

        # histograms data
        # it seems that a lot of this data has been poluted with FFs. I"ll remove them for now.
        histograms_pos = f.findall(b'REPLAYDATASET_SCORE')

        for pos_idx, pos in enumerate(histograms_pos, 1):
            print(f"\nProcessing histogram dataset {pos_idx}:")
            f.pos = pos + 19*8 #had to skip because of a bug somewhere. TODO: investigate
            # data_sets = f.read_int()
            data_sets = 27 #1B. has to be hardcoded because of a bug somewhere TODO: investigate
            print(f"Number of data sets: {data_sets}")

            histogram_labels[0] = 'REPLAYDATASET_SCORE'
            histograms[0] = {}

            print("\nReading histogram labels:")
            for i in range(1, data_sets):
                h = f.read_string_safe()
                print(f"Label {i}: {h}")
                histogram_labels[i] = h
                histograms[i] = {}

            n_ent = f.read_byte(3)
            print(f"\nProcessing {n_ent} entries:")

            for i in range(0, n_ent):
                n_data = f.read_byte(3)
                for j in range(0, n_data):
                    histograms[i][j] = {}
                    n_turns = f.read_byte(skip=3)
                    if n_turns > 0:
                        for k in range(0, n_turns):
                            turn = f.read_byte(skip=3)
                            value = f.read_byte(skip=3)
                            histograms[i][j][k] = value
                            print(f"    Turn {turn}: {value}")

            print(f"\nSaving histogram data to histograms.{pos}.pickle")
            jar = open('histograms.{0}.pickle'.format(pos), 'wb')
            pickle.dump(histograms, jar)
            jar.close()

if __name__ == "__main__":
    import sys
    parse(sys.argv[1])