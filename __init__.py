from itertools import chain
from os.path import join, exists
from mycroft.skills.skill_data import read_vocab_file
from mycroft.util import resolve_resource_file
import random
from mycroft.util import camel_case_split, create_daemon
from mycroft import MycroftSkill, intent_file_handler, intent_handler
from mycroft.skills.core import resting_screen_handler
from wallpaper_changer.search import latest_reddit, latest_wpcraft, \
    random_unsplash, latest_unsplash
from wallpaper_changer import set_wallpaper, get_desktop_environment
from mtranslate import translate
import re
from mycroft.util.parse import match_one
from adapt.intent import IntentBuilder


class WallpapersSkill(MycroftSkill):
    def __init__(self):
        super(WallpapersSkill, self).__init__(name='Wallpapers')
        # skill settings defaults
        if "auto_detect" not in self.settings:
            self.settings["auto_detect"] = True
        if "desktop_env" not in self.settings:
            self.settings["desktop_env"] = get_desktop_environment()
        if "rotate_wallpaper" not in self.settings:
            self.settings["rotate_wallpaper"] = True
        if "change_mins" not in self.settings:
            self.settings["change_mins"] = 30

        # imaage sources
        if "unsplash" not in self.settings:
            self.settings["unsplash"] = False
        if "wpcraft" not in self.settings:
            self.settings["wpcraft"] = True

        subs = ['/r/EarthPorn', '/r/BotanicalPorn', '/r/WaterPorn',
                    '/r/SeaPorn',
                    '/r/SkyPorn', '/r/FirePorn', '/r/DesertPorn',
                    '/r/WinterPorn',
                    '/r/AutumnPorn', '/r/WeatherPorn', '/r/GeologyPorn',
                    '/r/SpacePorn',
                    '/r/BeachPorn', '/r/MushroomPorn', '/r/SpringPorn',
                    '/r/SummerPorn',
                    '/r/LavaPorn', '/r/LakePorn', '/r/CityPorn',
                    '/r/VillagePorn',
                    '/r/RuralPorn', '/r/ArchitecturePorn', '/r/HousePorn',
                    '/r/CabinPorn',
                    '/r/ChurchPorn', '/r/AbandonedPorn', '/r/CemeteryPorn',
                    '/r/InfrastructurePorn', '/r/MachinePorn', '/r/CarPorn',
                    '/r/F1Porn',
                    '/r/MotorcyclePorn', '/r/MilitaryPorn', '/r/GunPorn',
                    '/r/KnifePorn',
                    '/r/BoatPorn', '/r/RidesPorn', '/r/DestructionPorn',
                    '/r/ThingsCutInHalfPorn', '/r/StarshipPorn',
                    '/r/ToolPorn',
                    '/r/TechnologyPorn', '/r/BridgePorn', '/r/PolicePorn',
                    '/r/SteamPorn',
                    '/r/RetailPorn', '/r/SpaceFlightPorn', '/r/roadporn',
                    '/r/drydockporn',
                    '/r/AnimalPorn', '/r/HumanPorn', '/r/EarthlingPorn',
                    '/r/AdrenalinePorn', '/r/ClimbingPorn', '/r/SportsPorn',
                    '/r/AgriculturePorn', '/r/TeaPorn', '/r/BonsaiPorn',
                    '/r/FoodPorn',
                    '/r/CulinaryPorn', '/r/DessertPorn', '/r/DesignPorn',
                    '/r/RoomPorn',
                    '/r/AlbumArtPorn', '/r/MetalPorn', '/r/MoviePosterPorn',
                    '/r/TelevisionPosterPorn', '/r/ComicBookPorn',
                    '/r/StreetArtPorn',
                    '/r/AdPorn', '/r/ArtPorn', '/r/FractalPorn',
                    '/r/InstrumentPorn',
                    '/r/ExposurePorn', '/r/MacroPorn', '/r/MicroPorn',
                    '/r/GeekPorn',
                    '/r/MTGPorn', '/r/GamerPorn', '/r/PowerWashingPorn',
                    '/r/AerialPorn',
                    '/r/OrganizationPorn', '/r/FashionPorn', '/r/AVPorn',
                    '/r/ApocalypsePorn', '/r/InfraredPorn', '/r/ViewPorn',
                    '/r/HellscapePorn', '/r/sculptureporn', '/r/HistoryPorn',
                    '/r/UniformPorn', '/r/BookPorn', '/r/NewsPorn',
                    '/r/QuotesPorn',
                    '/r/FuturePorn', '/r/FossilPorn', '/r/MegalithPorn',
                    '/r/ArtefactPorn',
                    '/r/AmateurEarthPorn', '/r/AmateurPhotography',
                    '/r/ArtistOfTheDay',
                    '/r/BackgroundArt', '/r/Conservation', '/r/EarthPornVids',
                    '/r/EyeCandy', '/r/FWEPP', '/r/ImaginaryLandscapes',
                    '/r/ImaginaryWildlands', '/r/IncredibleIndia',
                    '/r/ITookAPicture',
                    '/r/JoshuaTree', '/r/NationalGeographic', '/r/Nature',
                    '/r/NatureGifs',
                    '/r/NaturePics', '/r/NotSafeForNature', '/r/NZPhotos',
                    '/r/remoteplaces', '/r/Schweiz', '/r/SpecArt',
                    '/r/wallpapers',
                    "/r/InterstellarArt"]
        self.subs = [s.split("/")[-1].strip() for s in subs]
        self.wpcats = [
            '3d', 'abstract', 'animals', 'anime', "art", "black", "cars",
            'city',
            'dark', 'fantasy', 'flowers', 'food', 'holidays', 'love',
            'macro',
            'minimalism', 'motorcycles', 'music', 'nature', 'other',
            'smilies',
            'space', 'sport', 'hi-tech', 'textures', 'vector', 'words',
            '60_favorites'
        ]
        for c in self.subs:
            if c not in self.settings:
                self.settings[c] = True
        for c in self.wpcats:
            if c not in self.settings:
                self.settings[c] = True

        # state trackers
        self.pic_idx = 0
        self.picture_list = []
        self.translate_cache = {}
        self._old_settings = dict(self.settings)

        # events
        self.settings_change_callback = self._on_web_settings_change
        self.namespace = self.__class__.__name__.lower()
        self.skill_name = camel_case_split(self.__class__.__name__)

    def initialize(self):
        self.log.info("Detected desktop env " + self.settings["desktop_env"])

        # gui slideshow buttons
        self.gui.register_handler('skill-wallpapers.jarbasskills.next',
                                  self.handle_next)
        self.gui.register_handler('skill-wallpapers.jarbasskills.prev',
                                  self.handle_prev)

        # bigscreen homepage
        self.add_event('skill-wallpapers.jarbasskills.home',
                       self.homepage)

    # bigscreen
    def homepage(self):
        self.handle_random_picture()

    # idle screen
    def update_picture(self, query=None):
        data = {}
        if query is None:
            cats = list(self.subs)
            random.shuffle(cats)
            for c in cats:
                if data:
                    break
                idx = self.subs.index(c)
                if self.settings[c] and random.choice([True, False]):
                    wps = latest_reddit(self.subs[idx])
                    if wps:
                        random.shuffle(wps)
                        self.picture_list = wps
                        self.pic_idx = 0
                        data = wps[0]
                        data["url"] = "https://www.reddit.com/r/{s}/".format(s=c)
            if self.settings["unsplash"] and \
                    random.choice([True, False]) and not data:
                self.picture_list = latest_unsplash(query, n=3)
                data = self.picture_list[0]
                data["url"] = "https://source.unsplash.com/1920x1080/?" + query
                self.pic_idx = 0
            elif self.settings["wpcraft"] and \
                    random.choice([True, False]) and not data:
                wps = latest_wpcraft()
                random.shuffle(wps)
                data = wps[0]
                self.picture_list = wps
                self.pic_idx = 0
                data["url"] = "https://wallpaperscraft.com"
        else:
            # fuzzy match voc_files
            best_sub = query
            best_score = 0
            for s in self.subs:
                words = self.get_voc(s)
                sub, score = match_one(query, words)
                if score > best_score:
                    best_sub = sub
                    best_score = score
            if best_score > 0.85:
                query = best_sub

            # select subreddit
            if query in self.subs:
                wps = latest_reddit(query)
                if wps:
                    random.shuffle(wps)
                    self.picture_list = wps
                    self.pic_idx = 0
                    data = wps[0]
                    data["url"] = "https://www.reddit.com/r/{s}/".format(s=query)
            elif query in self.wpcats:
                wps = latest_wpcraft(query)
                random.shuffle(wps)
                data = wps[0]
                self.picture_list = wps
                self.pic_idx = 0
                data["url"] = "https://wallpaperscraft.com/catalog/" + query
            else:
                # no matching subreddit, search in unsplash
                self.picture_list = latest_unsplash(query, n=3)
                data = self.picture_list[0]
                data["url"] = "https://source.unsplash.com/1920x1080/?" + query
                self.pic_idx = 0

        if not data:
            # default source of wallpapers
            wps = latest_reddit("wallpapers")
            random.shuffle(wps)
            data = wps[0]
            self.picture_list = wps
            self.pic_idx = 0
            data["url"] = "https://www.reddit.com/r/wallpapers/"
        data = self._tx(data)

        for k in data:
            self.gui[k] = data[k]
        self.set_context("PhotoUpdated")
        return data["imgLink"], data.get("title", "")

    @resting_screen_handler("Wallpapers")
    def idle(self, message=None):
        image, title = self.update_picture()
        self.gui.show_image(image, fill='PreserveAspectFit')

    # skill internals
    def get_voc(self, voc_filename):
        # Check for both skill resources and mycroft-core resources
        voc = self.find_resource(voc_filename + '.voc', 'vocab')
        if not voc:  # Check for vocab in mycroft core resources
            voc = resolve_resource_file(join('text', self.lang,
                                             voc_filename + '.voc'))

        if not voc or not exists(voc):
            raise FileNotFoundError(
                'Could not find {}.voc file'.format(voc_filename))
        # load vocab and flatten into a simple list
        vocab = read_vocab_file(voc)
        return list(chain(*vocab))

    def _tx(self, data, base_lang="en"):
        keys = ["title"]
        for k in keys:
            if k not in data:
                continue
            data[k] = re.sub(r'\[.*?\]', '', data[k])
            data[k] = re.sub(r'\{.*?\}', '', data[k])
            data[k] = re.sub(r'\(.*?\)', '', data[k])
            data[k] = data[k].strip()
            if self.lang.split("-")[0] != base_lang:
                if data[k] not in self.translate_cache:
                    translated = translate(data[k], self.lang)
                    self.translate_cache[data[k]] = translated
                    data[k] = translated
                else:
                    data[k] = self.translate_cache[data[k]]
        return data

    def _on_web_settings_change(self):
        for k in self.settings:
            if self.settings[k] != self._old_settings[k]:
                self.handle_new_setting(k, self.settings[k],
                                        self._old_settings[k])
        self._old_settings = dict(self.settings)

    # on install
    def get_intro_message(self):
        # welcome dialog on skill install
        self.speak_dialog("intro", {"skill_name": self.skill_name})

    # intents
    def change_wallpaper(self, image):
        if self.settings["auto_detect"]:
            success = set_wallpaper(image)
        else:
            # allow user override of wallpaper command
            success = set_wallpaper(image, self.settings["desktop_env"])
            if not success:
                success = set_wallpaper(image)
        return success

    @intent_file_handler("wallpaper.random.intent")
    def handle_random_wallpaper(self, message):
        image, title = self.update_picture()
        success = self.change_wallpaper(image)
        if success:
            self.speak_dialog("wallpaper.changed")
        else:
            self.speak_dialog("wallpaper fail")
        self.gui.show_image(image, fill='PreserveAspectFit')

    @intent_file_handler("picture.random.intent")
    def handle_random_picture(self, message=None):
        self.update_picture()
        title = self.picture_list[self.pic_idx].get("title")
        if title:
            self.speak(title)
        self._display()

    @intent_file_handler("wallpaper.about.intent")
    def handle_wallpaper_about(self, message):
        query = message.data["query"]
        self.speak_dialog("searching", {"query": query})
        image, title = self.update_picture(query)

        if self.settings["auto_detect"]:
            success = set_wallpaper(image)
        else:
            # allow user override of wallpaper command
            success = set_wallpaper(image, self.settings["desktop_env"])
            if not success:
                success = set_wallpaper(image)
        if success:
            self.speak_dialog("wallpaper.changed")
        else:
            self.speak_dialog("wallpaper fail")
        self.gui.show_image(image, fill='PreserveAspectFit')

    @intent_file_handler("picture.about.intent")
    def handle_picture_about(self, message=None):
        query = message.data["query"]
        self.speak_dialog("searching", {"query": query})
        self.update_picture(query)
        title = self.picture_list[self.pic_idx].get("title")
        if title:
            self.speak(title)
        self._display()

    @intent_handler(IntentBuilder("NextPictureIntent")
                    .require("next").optionally("picture")
                    .require("SlideShow"))
    def handle_next(self, message=None):
        total = len(self.picture_list)
        self.pic_idx += 1
        if self.pic_idx >= total:
            self.pic_idx = total - 1
            self.speak_dialog("no.more.pictures")
        else:
            self._display()

    @intent_handler(IntentBuilder("PrevPictureIntent")
                    .require("previous").optionally("picture")
                    .require("SlideShow"))
    def handle_prev(self, message=None):
        self.pic_idx -= 1
        if self.pic_idx < 0:
            self.pic_idx = 0
            self.speak_dialog("no.more.pictures")
        else:
            title = self.picture_list[self.pic_idx].get("title")
            if title:
                self.speak(title)
            self._display()

    @intent_handler(IntentBuilder("MakeWallpaperIntent")
                    .require("set").require("wallpapers").optionally("picture")
                    .require("SlideShow"))
    def handle_set_wallpaper(self, message=None):
        image = self.picture_list[self.pic_idx]["imgLink"]
        success = self.change_wallpaper(image)
        if success:
            self.speak_dialog("wallpaper.changed")
        else:
            self.speak_dialog("wallpaper fail")

    def _display(self):
        self.gui.clear()
        data = self.picture_list[self.pic_idx]
        for k in data:
            self.gui[k] = data[k]
        title = self.picture_list[self.pic_idx].get("title")
        if title:
            self.speak(title)
        self.gui.show_page("slideshow.qml", override_idle=True)
        self.set_context("SlideShow")

    # event handlers
    def handle_new_setting(self, key, value, old_value):
        self.log.debug("{name}: {key} changed from {value} to {old}".format(
            key=key, value=value, old=old_value, name=self.skill_name))


def create_skill():
    return WallpapersSkill()
