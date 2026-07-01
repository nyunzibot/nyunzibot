import glob
import re

for f in glob.glob('commands/*.py'):
    with open(f, 'r', encoding='utf-8') as file:
        code = file.read()
    
    orig = code
    
    # 1. Standard else block
    code = code.replace('''            else:
                content = image_url
                # Check for video compression fallback (no file but successful fetch)
                if is_video_url(image_url):
                     content = f"Video compression failed, falling back to URL\\n{image_url}"
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())''',
'''            else:
                if is_video_url(image_url):
                     content = f"Video compression failed, falling back to URL\\n{image_url}"
                else:
                     content = ""
                     embed.set_image(url=image_url)
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())''')

    # 2. cuddle.py else block
    code = code.replace('''            else:
                if isinstance(image_url, list):
                    content = "\\n".join(image_url)
                else:
                    content = image_url
                    if is_video_url(image_url):
                        content = f"Video compression failed, falling back to URL\\n{image_url}"
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())''',
'''            else:
                if isinstance(image_url, list):
                    content = ""
                    embed.set_image(url=image_url[0])
                else:
                    if is_video_url(image_url):
                        content = f"Video compression failed, falling back to URL\\n{image_url}"
                    else:
                        content = ""
                        embed.set_image(url=image_url)
                msg = await interaction.edit_original_response(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())''')

    # 3. Standard 40005 block
    # msg = await interaction.edit_original_response(content=f"📦 File too large to attach\n{image_url}", embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())
    code = re.sub(
        r'msg = await interaction\.edit_original_response\(content=f\"📦 File too large to attach\\n\{image_url\}\", embed=embed, attachments=\[\](?:, view=view)?, allowed_mentions=discord\.AllowedMentions\.none\(\)\)',
        r'''content = "📦 File too large to attach"
                if is_video_url(image_url):
                    content += f"\\n{image_url}"
                else:
                    embed.set_image(url=image_url)
                msg = await interaction.edit_original_response(content=content, embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())''',
        code
    )

    # 4. cuddle.py 40005 block
    # msg = await interaction.edit_original_response(content=f"📦 File too large to attach\n{url_content}", embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())
    code = re.sub(
        r'msg = await interaction\.edit_original_response\(content=f\"📦 File too large to attach\\n\{url_content\}\", embed=embed, attachments=\[\], view=view, allowed_mentions=discord\.AllowedMentions\.none\(\)\)',
        r'''content = "📦 File too large to attach"
                if is_video_url(url_content):
                    content += f"\\n{url_content}"
                else:
                    embed.set_image(url=url_content)
                msg = await interaction.edit_original_response(content=content, embed=embed, attachments=[], view=view, allowed_mentions=discord.AllowedMentions.none())''',
        code
    )
    
    if code != orig:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(code)
        print(f"Updated {f}")
