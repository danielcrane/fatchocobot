import os
import discord
from dotenv import load_dotenv
import datetime
from firebase import firebase

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD = os.getenv("DISCORD_GUILD")


def printable_time_delta(delta):

    days = f"{delta.days} days, " if delta.days > 0 else ""
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    return f"{days}{hours} hours, {minutes} minutes"


class CustomClient(discord.Client):
    def __init__(self):
        self.TIME_FORMAT = "%H:%M %a, %b %d %Y (UTC)"
        self.WINDOWS = "!windows"
        self.TOD = "!tod"
        self.WINDOWS_RESPONSE = """
```
AQ      \t{aq_min} - {aq_max}\t ({aq_time})
Zaken   \t{zaken_min} - {zaken_max}\t ({zaken_time})
Baium   \t{baium_min} - {baium_max}\t ({baium_time})
Antharas\t{antharas_min} - {antharas_max}\t ({antharas_time})
Valakas\t{valakas_min} - {valakas_max}\t ({valakas_time})
Frintezza\t{frintezza_min} - {frintezza_max}\t ({frintezza_time})
```
        """

        self.SPAWN_TIMES = {
            "aq": (24 * 60, (24 + 6) * 60),
            "zaken": (40 * 60, (40 + 8) * 60),
            "baium": (120 * 60, (120 + 8) * 60),
            "antharas": (192 * 60, (192 + 8) * 60),
            "valakas": (264 * 60, (264 + 0) * 60),
            "frintezza": (48 * 60, (48 + 2) * 60),
        }

        self.BOSS_NAMES = {
            "aq": "Ant Queen",
            "zaken": "Zaken",
            "baium": "Baium",
            "antharas": "Antharas",
            "valakas": "Valakas",
            "frintezza": "Frintezza",
        }

        self.fb = firebase.FirebaseApplication("https://fatchocobot-2e402.firebaseio.com/", None)
        if self.fb.get("/raid-windows", "") is not None:
            result = self.fb.get("/raid-windows", "")
            self.fb_name = list(result.keys())[0]
            self.windows = result[self.fb_name]
        else:
            self.windows = {
                "aq": ("None", "None"),
                "zaken": ("None", "None"),
                "baium": ("None", "None"),
                "antharas": ("None", "None"),
                "valakas": ("None", "None"),
                "frintezza": ("None", "None"),
            }
            result = self.fb.post("/raid-windows", self.windows)
            self.fb_name = result["name"]

        super().__init__()

    def create_window_string(self, window):
        if window[0] == "None" or window[1] == "None":
            return "window unknown"

        now = datetime.datetime.now(datetime.timezone.utc)

        min_time = datetime.datetime.strptime(window[0], self.TIME_FORMAT).replace(
            tzinfo=datetime.timezone.utc
        )

        if min_time > now:
            # Case: window not opened yet
            return f"window opens in {printable_time_delta(min_time - now)}"

        max_time = datetime.datetime.strptime(window[1], self.TIME_FORMAT).replace(
            tzinfo=datetime.timezone.utc
        )

        if max_time > now:
            # Case: window still open
            return f"window closes in {printable_time_delta(max_time - now)}"
        else:
            # Case: window already closed
            return f"window closed {printable_time_delta(abs(max_time - now))} ago"

    async def on_message(self, message):
        if message.author == client.user:
            return
        content = message.content.lower()

        if content[: len(self.WINDOWS)] == self.WINDOWS:
            self.windows = self.fb.get("/raid-windows", "")[self.fb_name]
            aq_min, aq_max = self.windows["aq"]
            zaken_min, zaken_max = self.windows["zaken"]
            baium_min, baium_max = self.windows["baium"]
            antharas_min, antharas_max = self.windows["antharas"]
            valakas_min, valakas_max = self.windows["valakas"]
            frintezza_min, frintezza_max = self.windows["frintezza"]

            aq_time = self.create_window_string(self.windows["aq"])
            zaken_time = self.create_window_string(self.windows["zaken"])
            baium_time = self.create_window_string(self.windows["baium"])
            antharas_time = self.create_window_string(self.windows["antharas"])
            valakas_time = self.create_window_string(self.windows["valakas"])
            frintezza_time = self.create_window_string(self.windows["frintezza"])

            response = eval(f'f"""{self.WINDOWS_RESPONSE}"""')
            await message.channel.send(response)
            return

        if content[: len(self.TOD)] == self.TOD:
            content_split = content.split(" ")

            if len(content_split) < 4:
                await message.channel.send(
                    "Incorrect number of arguments for !tod, must follow format: `!tod <aq|zaken|baium|antharas> year/month/day hours:minutes` with hours in 24h format\n"
                    "For example: `!tod aq 2020/09/30 23:30`"
                )
                return

            boss_name = content_split[1].lower()
            time_of_death = " ".join(content_split[2:4])

            if boss_name in self.windows:
                t = datetime.datetime.strptime(time_of_death, "%Y/%m/%d %H:%M")
                spawn_times = self.SPAWN_TIMES[boss_name]
                self.windows[boss_name] = (
                    (t + datetime.timedelta(minutes=spawn_times[0])).strftime(self.TIME_FORMAT),
                    (t + datetime.timedelta(minutes=spawn_times[1])).strftime(self.TIME_FORMAT),
                )

                self.fb.put(f"/raid-windows/{self.fb_name}", boss_name, self.windows[boss_name])

                await message.channel.send(
                    f"Spawn time of {self.BOSS_NAMES[boss_name]} updated, new window:\n"
                    f"`{self.windows[boss_name][0]} - {self.windows[boss_name][1]}`"
                )
                return


client = CustomClient()
client.run(TOKEN)
