from typing import Optional

import requests
from ovos_bus_client.message import Message
from ovos_workshop.decorators import intent_handler, resting_screen_handler
from ovos_workshop.intents import IntentBuilder
from ovos_workshop.skills import OVOSSkill


def get_wallpapers(query: Optional[str] = None):
    url = "https://wallhaven.cc/api/v1/search"
    params = {"sorting": "random"}
    if query:
        params["q"] = query
    data = requests.get(url, params=params).json()["data"]
    return [w["path"] for w in data]


class WallpapersSkill(OVOSSkill):

    def initialize(self):
        # state trackers
        self.pic_idx = 0
        self.picture_list = []

        # gui slideshow buttons
        self.gui.register_handler(f'wallpaper.next', self.handle_next)
        self.gui.register_handler(f'wallpaper.prev', self.handle_prev)

        self.register_with_PHAL()

    # idle screen
    def fetch_wallpapers(self, query=None) -> str:
        self.picture_list = get_wallpapers(query)
        self.pic_idx = 0
        self.gui["imgLink"] = self.picture_list[self.pic_idx]
        self.set_context("PhotoUpdated")
        return self.picture_list[self.pic_idx]

    @resting_screen_handler("Wallpapers")
    def idle(self, message=None):
        image = self.fetch_wallpapers()
        self.gui.show_image(image, fill='PreserveAspectFit')

    # PHAL wallpaper manager integrations
    def register_with_PHAL(self):
        self.bus.emit(Message("ovos.wallpaper.manager.register.provider",
                              {"provider_name": self.skill_id,
                               "provider_display_name": self.name}))
        self.bus.on(f"{self.skill_id}.get.wallpaper.collection", self.handle_wallpaper_scan)
        self.bus.on(f"{self.skill_id}.get.new.wallpaper", self.handle_wallpaper_get)
        self.fetch_wallpapers()
        self.bus.emit(Message("ovos.wallpaper.manager.collect.collection.response",
                              {"provider_name": self.skill_id,
                               "wallpaper_collection": self.picture_list}))

    def handle_wallpaper_scan(self, message: Message):
        self.fetch_wallpapers()
        self.bus.emit(message.reply("ovos.wallpaper.manager.collect.collection.response",
                                    {"provider_name": self.skill_id,
                                     "wallpaper_collection": self.picture_list}))

    def handle_wallpaper_get(self, message: Message):
        url = self.fetch_wallpapers()
        self.bus.emit(message.reply("ovos.wallpaper.manager.set.wallpaper",
                                    {"provider_name": self.skill_id,
                                     "url": url}))

    # skill internals
    def change_wallpaper(self, image):
        # update in homescreen skill / PHAL plugin
        self.bus.emit(Message("ovos.wallpaper.manager.set.wallpaper",
                              {"provider_name": self.skill_id, "url": image}))
        self.bus.emit(Message("homescreen.wallpaper.set", {"url": image}))

    # intents
    @intent_handler("wallpaper.random.intent")
    def handle_random_wallpaper(self, message):
        image = self.fetch_wallpapers()
        self.change_wallpaper(image)
        self.speak_dialog("wallpaper.changed")

    @intent_handler("picture.random.intent")
    def handle_random_picture(self, message=None):
        image = self.fetch_wallpapers()
        self.gui.show_image(image)

    @intent_handler("wallpaper.about.intent")
    def handle_wallpaper_about(self, message):
        query = message.data["query"]
        self.speak_dialog("searching", {"query": query})
        image = self.fetch_wallpapers(query)
        self.change_wallpaper(image)
        self.speak_dialog("wallpaper.changed")

    @intent_handler("picture.about.intent")
    def handle_picture_about(self, message=None):
        query = message.data["query"]
        self.speak_dialog("searching", {"query": query})
        image = self.fetch_wallpapers(query)
        self.gui.show_image(image)

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
            image = self.picture_list[self.pic_idx]
            self.gui.show_image(image)

    @intent_handler(IntentBuilder("PrevPictureIntent")
                    .require("previous").optionally("picture")
                    .require("SlideShow"))
    def handle_prev(self, message=None):
        self.pic_idx -= 1
        if self.pic_idx < 0:
            self.pic_idx = 0
            self.speak_dialog("no.more.pictures")
        else:
            image = self.picture_list[self.pic_idx]
            self.gui.show_image(image)

    @intent_handler(IntentBuilder("MakeWallpaperIntent")
                    .require("set").require("wallpapers").optionally("picture")
                    .require("SlideShow"))
    def handle_set_wallpaper(self, message=None):
        image = self.picture_list[self.pic_idx]
        self.change_wallpaper(image)
        self.speak_dialog("wallpaper.changed")
