import glob
import re

for f in glob.glob('commands/*.py'):
    with open(f, 'r', encoding='utf-8') as file:
        code = file.read()
    
    orig = code
    
    # We will search for where we previously added `embed.set_image(url=image_url)` 
    # and we will inject the description append.

    # 1. Standard else block
    code = code.replace('''            else:
                if is_video_url(image_url):
                     content = f"Video compression failed, falling back to URL\\n{image_url}"
                else:
                     content = ""
                     embed.set_image(url=image_url)
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())''',
'''            else:
                if is_video_url(image_url):
                     content = f"Video compression failed, falling back to URL\\n{image_url}"
                else:
                     content = ""
                     embed.set_image(url=image_url)
                     embed.description = str(embed.description or "") + f"\\n\\n[Direct Media Link]({image_url})"
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())''')

    # 2. cuddle.py else block
    code = code.replace('''            else:
                if isinstance(image_url, list):
                    content = ""
                    embed.set_image(url=image_url[0])
                else:
                    if is_video_url(image_url):
                        content = f"Video compression failed, falling back to URL\\n{image_url}"
                    else:
                        content = ""
                        embed.set_image(url=image_url)
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())''',
'''            else:
                if isinstance(image_url, list):
                    content = ""
                    embed.set_image(url=image_url[0])
                    embed.description = str(embed.description or "") + f"\\n\\n[Direct Media Link]({image_url[0]})"
                else:
                    if is_video_url(image_url):
                        content = f"Video compression failed, falling back to URL\\n{image_url}"
                    else:
                        content = ""
                        embed.set_image(url=image_url)
                        embed.description = str(embed.description or "") + f"\\n\\n[Direct Media Link]({image_url})"
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())''')

    # 3. Standard 40005 block
    code = code.replace('''                if is_video_url(image_url):
                    content += f"\\n{image_url}"
                else:
                    embed.set_image(url=image_url)
                msg = await interaction.edit_original_response(content=content, embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())''',
'''                if is_video_url(image_url):
                    content += f"\\n{image_url}"
                else:
                    embed.set_image(url=image_url)
                    embed.description = str(embed.description or "") + f"\\n\\n[Direct Media Link]({image_url})"
                msg = await interaction.edit_original_response(content=content, embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())''')

    # 4. cuddle.py 40005 block
    code = code.replace('''                if is_video_url(_url):
                    content += f"\\n{_url}"
                else:
                    embed.set_image(url=_url)
                msg = await interaction.edit_original_response(content=content, embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())''',
'''                if is_video_url(_url):
                    content += f"\\n{_url}"
                else:
                    embed.set_image(url=_url)
                    embed.description = str(embed.description or "") + f"\\n\\n[Direct Media Link]({_url})"
                msg = await interaction.edit_original_response(content=content, embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())''')
    
    if code != orig:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(code)
        print(f"Updated {f}")
