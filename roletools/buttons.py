from __future__ import annotations

import discord
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.commands import Context
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import pagify
from .toggle_button import ToggleRoleButton

from .abc import RoleToolsMixin
from .components import ButtonRole, RoleToolsView
from .converter import ButtonFlags, RoleHierarchyConverter
from .menus import BaseMenu, ButtonRolePages

roletools = RoleToolsMixin.roletools

log = getLogger("red.Trusty-cogs.RoleTools")
_ = Translator("RoleTools", __file__)


class RoleToolsButtons(RoleToolsMixin):
    """This class handles setting up button roles"""

    async def initialize_buttons(self):
        for guild_id, settings in self.settings.items():
            if guild_id not in self.views:
                log.trace("Adding guild ID %s to views in buttons", guild_id)
                self.views[guild_id] = {}
            for button_name, button_data in settings["buttons"].items():
                log.verbose("Adding Button %s", button_name)
                guild = self.bot.get_guild(guild_id)
                for message_id in set(button_data.get("messages", [])):
                    # Toggle-Button
                    if button_data.get("type") == "toggle":
                        role1 = guild.get_role(button_data["role1_id"])
                        role2 = guild.get_role(button_data["role2_id"])
                        style = discord.ButtonStyle(button_data["style"])
                        label = button_data["label"]
                        button = ButtonRole(
                            style=button_data["style"],
                            label=button_data["label"],
                            emoji=emoji,
                            custom_id=f"{button_name}-{button_data['role_id']}",
                            role_id=button_data["role_id1"],
                            name=button_name,
                        )
                    else:
                        # Normaler ButtonRole
                        emoji = button_data.get("emoji")
                        if emoji is not None:
                            emoji = discord.PartialEmoji.from_str(emoji)
                        button = ButtonRole(
                            style=button_data["style"],
                            label=button_data["label"],
                            emoji=emoji,
                            custom_id=f"{button_name}-{button_data['role_id']}",
                            role_id=button_data["role_id"],
                            name=button_name,
                        )
                        if guild is not None:
                            button.replace_label(guild)
                    # View erzeugen/füllen
                    if message_id not in self.views[guild_id]:
                        log.trace("Creating view for button %s", button_name)
                        self.views[guild_id][message_id] = RoleToolsView(self)
                    # Duplikate vermeiden
                    custom_id = getattr(button, "custom_id", None)
                    if custom_id is not None:
                        existing_ids = {getattr(c, "custom_id", None) for c in self.views[guild_id][message_id].children}
                        if custom_id in existing_ids:
                            continue
                    try:
                        self.views[guild_id][message_id].add_item(button)
                    except ValueError:
                        log.error(
                            "There was an error adding button %s on message https://discord.com/channels/%s/%s",
                            button.name,
                            guild_id,
                            message_id.replace("-", "/"),
                        )

    @roletools.group(name="buttons", aliases=["button"], with_app_command=False)
    @commands.admin_or_permissions(manage_roles=True)
    async def buttons(self, ctx: Context) -> None:
        """
        Setup role buttons
        """

    @buttons.command(name="create", usage="<name> <role> [extras]")
    async def create_button(
        self,
        ctx: Context,
        name: str,
        role: RoleHierarchyConverter,
        *,
        extras: ButtonFlags,
    ) -> None:
        """
        Create a role button

        - `<name>` - The name of the button for use later in setup.
        - `<role>` - The role this button will assign or remove.
        - `[extras]`
         - `label:` - The optional label for the button.
         - `emoji:` - The optional emoji used in the button.
         - `style:` - The background button style. Must be one of the following:
           - `primary`
           - `secondary`
           - `success`
           - `danger`
           - `blurple`
           - `grey`
           - `green`
           - `red`

        Note: If no label and no emoji are provided the roles name will be used instead.
        This name will not update if the role name is changed.

        Example:
            `[p]roletools button create role1 @role label: Super fun role style: blurple emoji: 😀`
        """
        if " " in name:
            await ctx.send(_("There cannot be a space in the name of a button."))
            return
        if ctx.guild.id not in self.views:
            self.views[ctx.guild.id] = {}
        emoji_id = None
        if extras.emoji is not None:
            if not isinstance(extras.emoji, discord.PartialEmoji):
                try:
                    await ctx.message.add_reaction(extras.emoji)
                    emoji_id = str(extras.emoji)
                except Exception:
                    emoji_id = None
            else:
                emoji_id = f"{extras.emoji.name}:{extras.emoji.id}"
                if extras.emoji.animated:
                    emoji_id = f"a:{emoji_id}"
        label = extras.label or ""
        if not emoji_id and not label:
            label = f"@{role.name}"

        button_settings = {
            "role_id": role.id,
            "label": label,
            "emoji": emoji_id,
            "style": extras.style.value,
            "name": name.lower(),
            "messages": [],
        }
        custom_id = f"{name.lower()}-{role.id}"
        async with self.config.guild(ctx.guild).buttons() as buttons:
            if name.lower() in buttons and buttons[name.lower()]["role_id"] == role.id:
                # only transfer messages settings and fix old buttons if the role ID has not changed
                # this will allow for seamlessly modifying a buttons look
                button_settings["messages"] = buttons[name.lower()]["messages"]
            buttons[name.lower()] = button_settings

        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = await self.config.guild(ctx.guild).all()
        self.settings[ctx.guild.id]["buttons"][name.lower()] = button_settings
        async with self.config.role(role).buttons() as buttons:
            if name.lower() not in buttons:
                buttons.append(name.lower())
        button = ButtonRole(
            style=extras.style.value,
            label=label,
            emoji=emoji_id,
            custom_id=custom_id,
            role_id=role.id,
            name=name.lower(),
        )
        failed_fixes = []
        for message_id in button_settings["messages"]:
            # fix old buttons with the new one when interacted with
            replacement_view = self.views.get(ctx.guild.id, {}).get(message_id, None)
            if replacement_view is None:
                continue
            for item in replacement_view.children:
                if item.custom_id == custom_id:
                    replacement_view.remove_item(item)
            try:
                replacement_view.add_item(button)
            except ValueError:
                failed_fixes.append(message_id)
        button.replace_label(ctx.guild)
        view = RoleToolsView(self, timeout=180.0)
        view.add_item(button)
        await ctx.send("Here is how your button will look.", view=view)
        if failed_fixes:
            msg = ""
            for view_id in failed_fixes:
                channel_id, message_id = view_id.split("-")
                channel = ctx.guild.get_channel(int(channel_id))
                if channel is None:
                    continue
                message = discord.PartialMessage(channel=channel, id=int(message_id))
                msg += f"- {message.jump_url}\n"
            pages = []
            full_msg = _(
                "The following existing buttons could not be edited with the new settings.\n{failed}"
            ).format(failed=msg)
            for page in pagify(full_msg):
                pages.append(page)
            await ctx.send_interactive(pages)
        await self.confirm_selfassignable(ctx, [role])

    @buttons.command(name="delete", aliases=["del", "remove"])
    async def delete_button(self, ctx: Context, *, name: str) -> None:
        """
        Delete a saved button.
    
        `<name>` - the name of the button you want to delete.
        """
        if ctx.guild.id not in self.views:
            self.views[ctx.guild.id] = {}
        async with self.config.guild(ctx.guild).buttons() as buttons:
            if name in buttons:
                button_data = buttons[name]
                # Toggle-Button?
                if button_data.get("type") == "toggle":
                    # Toggle-Buttons haben zwei Rollen
                    role_id_1 = button_data["role1_id"]
                    role_id_2 = button_data["role2_id"]
                    custom_id_1 = f"{name.lower()}-{role_id_1}"
                    custom_id_2 = f"{name.lower()}-{role_id_2}"
                    # Deaktiviere alle Instanzen des Buttons in allen Views (für beide Rollen)
                    for view in self.views[ctx.guild.id].values():
                        for child in view.children:
                            if getattr(child, "custom_id", None) in [custom_id_1, custom_id_2]:
                                child.disabled = True
                    # Entferne aus settings/registry
                    if name in self.settings.get(ctx.guild.id, {}).get("buttons", {}):
                        del self.settings[ctx.guild.id]["buttons"][name]
                    del buttons[name]
                    # Entferne aus allen Rollen-Registries (falls vorhanden)
                    async with self.config.role_from_id(role_id_1).buttons() as role_buttons_1:
                        if name in role_buttons_1:
                            role_buttons_1.remove(name)
                    async with self.config.role_from_id(role_id_2).buttons() as role_buttons_2:
                        if name in role_buttons_2:
                            role_buttons_2.remove(name)
                    msg = _("Toggle-Button `{name}` has been deleted.").format(name=name)
                else:
                    # Normaler Button wie gehabt
                    role_id = button_data["role_id"]
                    custom_id = f"{name.lower()}-{role_id}"
                    for view in self.views[ctx.guild.id].values():
                        for child in view.children:
                            if getattr(child, "custom_id", None) == custom_id:
                                child.disabled = True
                    if name in self.settings.get(ctx.guild.id, {}).get("buttons", {}):
                        del self.settings[ctx.guild.id]["buttons"][name]
                    del buttons[name]
                    async with self.config.role_from_id(role_id).buttons() as role_buttons:
                        if name in role_buttons:
                            role_buttons.remove(name)
                    msg = _("Button `{name}` has been deleted.").format(name=name)
            else:
                msg = _("Button `{name}` doesn't appear to exist.").format(name=name)
        await ctx.send(msg)

    @buttons.command(name="view")
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(read_message_history=True, add_reactions=True)
    async def button_roles_view(self, ctx: Context) -> None:
        """
        View current buttons setup for role assign in this server.
        """
        no_buttons = _("There are no button roles on this server.")
        if ctx.guild.id not in self.settings or not self.settings[ctx.guild.id].get("buttons"):
            await ctx.send(no_buttons)
            return
    
        pages = []
        colour_index = {
            1: "blurple",
            2: "grey",
            3: "green",
            4: "red",
        }
    
        for name, button_data in self.settings[ctx.guild.id]["buttons"].items():
            # Toggle-Button anzeigen
            if button_data.get("type") == "toggle":
                role1 = ctx.guild.get_role(button_data["role1_id"])
                role2 = ctx.guild.get_role(button_data["role2_id"])
                style = colour_index.get(button_data["style"], button_data["style"])
                msg = _(
                    "**Toggle-Button in {guild}**\n"
                    "**Name:** {name}\n"
                    "**Rollen:** {role1} ↔ {role2}\n"
                    "**Label:** {label}\n"
                    "**Style:** {style}\n"
                ).format(
                    guild=ctx.guild.name,
                    name=name,
                    role1=role1.mention if role1 else _("Fehlt"),
                    role2=role2.mention if role2 else _("Fehlt"),
                    label=button_data["label"],
                    style=style,
                )
                for messages in button_data.get("messages", []):
                    channel_id, msg_id = messages.split("-")
                    channel = ctx.guild.get_channel(int(channel_id))
                    if channel:
                        message_url = f"https://discord.com/channels/{ctx.guild.id}/{channel_id}/{msg_id}"
                    else:
                        message_url = "None"
                    msg += _("[Button Message]({message})\n").format(message=message_url)
            else:
                # Normale Button-Ausgabe wie bisher
                role = ctx.guild.get_role(button_data["role_id"])
                emoji = button_data["emoji"]
                if emoji is not None:
                    emoji = discord.PartialEmoji.from_str(emoji)
                style = colour_index.get(button_data["style"], button_data["style"])
                msg = _("Button Roles in {guild}\n").format(guild=ctx.guild.name)
                msg += _(
                    "**Name:** {name}\n**Role:** {role}\n**Label:** {label}\n"
                    "**Style:** {style}\n**Emoji:** {emoji}\n"
                ).format(
                    name=name,
                    role=role.mention if role else _("Missing Role"),
                    label=button_data["label"],
                    style=style,
                    emoji=emoji,
                )
                for messages in button_data.get("messages", []):
                    channel_id, msg_id = messages.split("-")
                    channel = ctx.guild.get_channel(int(channel_id))
                    if channel:
                        message_url = f"https://discord.com/channels/{ctx.guild.id}/{channel_id}/{msg_id}"
                    else:
                        message_url = "None"
                    msg += _("[Button Message]({message})\n").format(message=message_url)
            pages.append(msg)
    
        if not pages:
            await ctx.send(no_buttons)
            return
    
        await BaseMenu(
            source=ButtonRolePages(pages=pages),
            delete_message_after=False,
            clear_reactions_after=True,
            timeout=60,
            cog=self,
            page_start=0,
        ).start(ctx=ctx)
    @buttons.command(name="toggle", usage="<name> <role1> <role2> [extras]")
    async def create_toggle_button(
        self,
        ctx: Context,
        name: str,
        role1: RoleHierarchyConverter,
        role2: RoleHierarchyConverter,
        *,
        extras: ButtonFlags,   # Optional für Label/Style/Emoji
    ) -> None:
        """
        Create a toggle role button
    
        [p]roletools buttons toggle <name> <role1> <role2> [extras]
        Beispiel:
            [p]roletools buttons toggle hockeyfan @Rolle1 @Rolle2 label: Hockeyfan style: green
        """
    
        label = (getattr(extras, "label", "") or "").strip() or f"{role1.name} ↔ {role2.name}"
        style = getattr(extras, "style", discord.ButtonStyle.secondary)
        if isinstance(style, int):
            style = discord.ButtonStyle(style)
    
        # 1. Toggle-Daten speichern
        toggle_settings = {
            "role1_id": role1.id,
            "role2_id": role2.id,
            "label": label.value,
            "style": style.value,
            "name": name.lower(),
            "type": "toggle",           # <-- Wichtig: als Toggle markieren!
            "messages": [],
        }
        custom_id = f"{name.lower()}-{role1.id}"
        async with self.config.guild(ctx.guild).buttons() as buttons:
            buttons[name.lower()] = toggle_settings
        if ctx.guild.id not in self.settings:
            self.settings[ctx.guild.id] = await self.config.guild(ctx.guild).all()
        self.settings[ctx.guild.id]["buttons"][name.lower()] = toggle_settings
    
        # 2. Preview (wie gehabt)
        view = discord.ui.View(timeout=180.0)
        view.add_item(ToggleRoleButton(role1, role2, label=label, style=style))
        embed = discord.Embed(
            title="Level System",
            description="Hier kannst du entscheiden ob du das Level System für dich aktivieren oder deaktivieren möchtest.",
            color=discord.Color.green()  # oder eine andere Farbe
        )
        await ctx.send(embed=embed, view=view)
    @buttons.command(name="cleanup")
    @commands.admin_or_permissions(manage_roles=True)
    @commands.bot_has_permissions(read_message_history=True)
    async def button_cleanup(self, ctx: commands.Context):
        """
        Check each button that has registered a message still exists and remove buttons with
        missing messages.

        # Note: This will also potentially cause problems if the button exists in a thread
        it will not be found if the thread is archived and subsequently removed.
        """
        guild = ctx.guild
        async with ctx.typing():
            async with self.config.guild(guild).buttons() as buttons:
                for name, button_settings in self.settings[guild.id].get("buttons", {}).items():
                    messages = set(button_settings["messages"])
                    for message_ids in button_settings["messages"]:
                        try:
                            channel_id, message_id = message_ids.split("-")
                            channel = guild.get_channel_or_thread(int(channel_id))
                            # threads shouldn't be used and this will break if the thread
                            # in question is archived
                            if channel is None:
                                messages.remove(message_ids)
                                continue
                            await channel.fetch_message(int(message_id))
                        except discord.Forbidden:
                            # We can't confirm the message doesn't exist with this
                            continue
                        except (discord.NotFound, discord.HTTPException):
                            messages.remove(message_ids)
                            log.info(
                                "Removing %s message reference on %s button %s since it can't be found.",
                                message_ids,
                                name,
                                guild.id,
                            )
                        except Exception:
                            log.exception(
                                "Error attempting to remove a message reference on select menu %s",
                                name,
                            )
                            continue
                    buttons[name]["messages"] = list(messages)
                    self.settings[guild.id]["buttons"][name]["messages"] = list(messages)
        await ctx.send(_("I am finished deleting old button message references."))

