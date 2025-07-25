import discord

class ToggleRoleButton(discord.ui.Button):
    def __init__(self, role1: discord.Role, role2: discord.Role, label: str = None, style: discord.ButtonStyle = discord.ButtonStyle.primary):
        super().__init__(label=label or f"{role1.name} ↔ {role2.name}", style=style)
        self.role1 = role1
        self.role2 = role2

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        guild = interaction.guild

        # Ensure bot has permissions
        if not guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("Ich habe keine Rechte, Rollen zu vergeben!", ephemeral=True)
            return

        # Toggle logic
        if self.role1 in member.roles:
            await member.remove_roles(self.role1, reason="Role toggle via button")
            await member.add_roles(self.role2, reason="Role toggle via button")
            await interaction.response.send_message(f"Du hast jetzt die Rolle {self.role2.mention}!", ephemeral=True)
        elif self.role2 in member.roles:
            await member.remove_roles(self.role2, reason="Role toggle via button")
            await member.add_roles(self.role1, reason="Role toggle via button")
            await interaction.response.send_message(f"Du hast jetzt die Rolle {self.role1.mention}!", ephemeral=True)
        else:
            await member.add_roles(self.role1, reason="Role toggle via button")
            await interaction.response.send_message(f"Du hast jetzt die Rolle {self.role1.mention}!", ephemeral=True)
