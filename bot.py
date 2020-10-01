import os
import discord
from dotenv import load_dotenv
import datetime
import json

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
        self.TIME = "!time"
        self.WINDOWS = "!windows"
        self.TOD = "!tod"
        self.WINDOWS_RESPONSE = """
```
AQ      \t{aq_min} - {aq_max}\t ({aq_time})
Zaken   \t{zaken_min} - {zaken_max}\t ({zaken_time})
Baium   \t{baium_min} - {baium_max}\t ({baium_time})
Antharas\t{antharas_min} - {antharas_max}\t ({antharas_time})
```
        """

        self.SPAWN_TIMES = {
            "aq": (24 * 60, (24 + 6) * 60),
            "zaken": (40 * 60, (40 + 8) * 60),
            "baium": (120 * 60, (120 + 8) * 60),
            "antharas": (192 * 60, (192 + 8) * 60),
        }

        self.BOSS_NAMES = {
            "aq": "Ant Queen",
            "zaken": "Zaken",
            "baium": "Baium",
            "antharas": "Antharas",
        }

        if os.path.isfile("windows.json"):
            with open("windows.json", "r") as f:
                self.windows = json.load(f)
        else:
            self.windows = {
                "aq": (None, None),
                "zaken": (None, None),
                "baium": (None, None),
                "antharas": (None, None),
            }
        super().__init__()

    def create_window_string(self, window):
        if window[0] is None or window[1] is None:
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

        if self.TIME in content:
            time_idx = content.index(self.TIME)
            t = datetime.datetime.now(datetime.timezone.utc)

            if (
                len(content) > time_idx + len(TIME) + 1
                and content[time_idx + len(TIME) + 1] == "-"
            ):
                minutes = int(content[time_idx + len(self.TIME) + 2 :].split(" ")[0])
                t -= datetime.timedelta(minutes=minutes)

            await message.channel.send(t.strftime(self.TIME_FORMAT))
            return

        if content[: len(self.WINDOWS)] == self.WINDOWS:
            aq_min, aq_max = self.windows["aq"]
            zaken_min, zaken_max = self.windows["zaken"]
            baium_min, baium_max = self.windows["baium"]
            antharas_min, antharas_max = self.windows["antharas"]

            aq_time = self.create_window_string(self.windows["aq"])
            zaken_time = self.create_window_string(self.windows["zaken"])
            baium_time = self.create_window_string(self.windows["baium"])
            antharas_time = self.create_window_string(self.windows["antharas"])

            response = eval(f'f"""{self.WINDOWS_RESPONSE}"""')
            await message.channel.send(response)
            return

        if content[: len(self.TOD)] == self.TOD:
            content_split = content.split(" ")
            print(content_split)

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

                with open("windows.json", "w") as f:
                    json.dump(self.windows, f)

                await message.channel.send(
                    f"Spawn time of {self.BOSS_NAMES[boss_name]} updated, new window:\n"
                    f"`{self.windows[boss_name][0]} - {self.windows[boss_name][1]}`"
                )
                return


client = CustomClient()
client.run(TOKEN)
