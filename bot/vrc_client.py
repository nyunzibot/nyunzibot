import logging
import asyncio
from typing import Optional, List, Tuple
from config import VRC_USERNAME, VRC_PASSWORD, USER_AGENT

log = logging.getLogger("nyunzi")

class VRChatClient:
    def __init__(self):
        self.username = VRC_USERNAME
        self.password = VRC_PASSWORD
        self.api_client = None
        self.auth_api = None
        self.users_api = None
        self.files_api = None
        self.friends_api = None
        self.ready = False
        self.friends_cache: List[Tuple[str, str]] = []  # (display_name, id)

    async def initialize(self) -> bool:
        """Initialize the VRChat API client and attempt to authenticate asynchronously."""
        if not self.username or not self.password:
            log.warning("VRC_USERNAME or VRC_PASSWORD is not set. VRChat features will be disabled.")
            return False

        def _sync_init():
            import vrchatapi
            from vrchatapi.api import authentication_api, users_api, files_api, friends_api
            from vrchatapi.exceptions import ApiException, UnauthorizedException
            from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
            import pyotp
            
            configuration = vrchatapi.Configuration(
                username=self.username,
                password=self.password,
            )
            
            # Using the required User-Agent format
            self.api_client = vrchatapi.ApiClient(configuration)
            self.api_client.user_agent = f"{USER_AGENT} contact@nyunzibot.local"
            
            self.auth_api = authentication_api.AuthenticationApi(self.api_client)
            self.users_api = users_api.UsersApi(self.api_client)
            self.files_api = files_api.FilesApi(self.api_client)
            self.friends_api = friends_api.FriendsApi(self.api_client)
            
            # Attempt to login
            try:
                current_user = self.auth_api.get_current_user()
            except UnauthorizedException as e:
                from config import VRC_TOTP_SECRET
                if "2 Factor Authentication" in e.reason and VRC_TOTP_SECRET:
                    log.info("VRChat requires 2FA. Generating TOTP code...")
                    totp = pyotp.TOTP(VRC_TOTP_SECRET)
                    code = totp.now()
                    self.auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(code=code))
                    current_user = self.auth_api.get_current_user()
                else:
                    raise e
                    
            log.info(f"Successfully authenticated to VRChat as {current_user.display_name}")
            return True

        try:
            self.ready = await asyncio.to_thread(_sync_init)
            if self.ready:
                # Start background task to update friends
                asyncio.create_task(self._friend_update_loop())
            return self.ready
            
        except Exception as e:
            log.error(f"Failed to authenticate with VRChat API: {e}")
            self.ready = False
            return False

    async def _friend_update_loop(self):
        """Periodically update the friends cache (every 5 minutes to respect rate limits)"""
        while self.ready:
            try:
                def _fetch():
                    import vrchatapi
                    # Fetch online friends
                    online = self.friends_api.get_friends(n=100, offline=False)
                    # Fetch offline friends
                    offline = self.friends_api.get_friends(n=100, offline=True)
                    return online + offline
                
                friends = await asyncio.to_thread(_fetch)
                # Use a dict to deduplicate just in case, though they should be mutually exclusive
                deduped = {f.id: f.display_name for f in friends}
                self.friends_cache = [(name, vid) for vid, name in deduped.items()]
                self.friends_cache.sort(key=lambda x: x[0].lower()) # sort alphabetically
                log.info(f"VRChat friends cache updated, found {len(self.friends_cache)} friends.")
            except Exception as e:
                log.error(f"Failed to fetch VRChat friends: {e}")
            
            await asyncio.sleep(300) # 5 minutes

    def search_friends(self, query: str) -> List[Tuple[str, str]]:
        """Search the friends cache for a given query (case-insensitive)"""
        q = query.lower()
        return [(name, vid) for name, vid in self.friends_cache if q in name.lower()][:25]

    async def upload_emoji_and_boop(
        self, target_user_id: str, image_bytes: bytes, filename: str,
        frames: int = 0, frames_over_time: int = 0
    ) -> tuple[bool, str]:
        """
        Uploads an image as an emoji and boops the target user.
        """
        if not self.ready:
            return False, "VRChat client is not authenticated."
            
        def _sync_task():
            import tempfile
            import os
            try:
                # 1. Upload the image/sprite sheet
                log.info(f"Uploading file '{filename}' to VRChat...")
                
                # We write bytes to a temp file because vrchatapi client expects a file path for uploads
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename.split('.')[-1]}") as tmp:
                    tmp.write(image_bytes)
                    tmp_path = tmp.name
                    
                try:
                    form_params = [
                        ('file', (filename, open(tmp_path, 'rb').read(), 'image/png')),
                        ('tag', 'emojianimated' if frames > 0 else 'emoji')
                    ]
                    if frames > 0:
                        form_params.append(('frames', str(frames)))
                        form_params.append(('framesOverTime', str(frames_over_time)))
                        
                    # Direct API call for image upload (since files_api might use the chunked version)
                    # NOTE: Python requests is cleaner for multipart but we can use api_client if it supports it.
                    # call_api expects post_params instead of files
                    # Let's use call_api
                    post_params = [('tag', 'emoji')]
                    if frames > 0:
                        post_params.append(('frames', str(frames)))
                        post_params.append(('framesOverTime', str(frames_over_time)))
                    
                    # animationStyle is not typically needed for animated sprite sheets (or causes panning issues)
                    # For static, you can use stop. Let's just always use 'stop' to prevent weird UV panning.
                    post_params.append(('animationStyle', 'stop'))
                        
                    try:
                        import vrchatapi
                        response = self.api_client.call_api(
                            '/file/image', 'POST',
                            header_params={'Content-Type': 'multipart/form-data'},
                            auth_settings=['authCookie'],
                            post_params=post_params,
                            files={'file': tmp_path},
                            response_types_map={200: None}
                        )
                    except vrchatapi.rest.ApiException as e:
                        if e.status == 400 and "18 saved emoji" in str(e.body):
                            log.info("Hit 18 emoji limit, attempting to clean up old emojis...")
                            if self._cleanup_old_emojis():
                                # Retry
                                response = self.api_client.call_api(
                                    '/file/image', 'POST',
                                    header_params={'Content-Type': 'multipart/form-data'},
                                    auth_settings=['authCookie'],
                                    post_params=post_params,
                                    files={'file': tmp_path},
                                    response_types_map={200: None}
                                )
                            else:
                                raise
                        else:
                            raise
                    
                    emoji_id = None
                    if self.api_client.last_response and self.api_client.last_response.data:
                        import json
                        try:
                            resp_json = json.loads(self.api_client.last_response.data)
                            emoji_id = resp_json.get('id')
                            log.info(f"Extracted emoji ID: {emoji_id}")
                        except Exception as e:
                            log.warning(f"Failed to parse emoji ID: {e}")
                finally:
                    os.remove(tmp_path)
                
                # 2. Boop the user
                log.info(f"Sending boop to {target_user_id}...")
                
                try:
                    body = {}
                    if emoji_id:
                        body['emojiId'] = emoji_id
                    
                    self.api_client.call_api(
                        '/users/{userId}/boop', 'POST',
                        path_params={'userId': target_user_id},
                        auth_settings=['authCookie'],
                        body=body,
                        response_types_map={200: None}
                    )
                except vrchatapi.rest.ApiException as e:
                    if e.status == 429:
                        if e.body and "already booped" in str(e.body).lower():
                            log.info("User was already booped recently, treating as success.")
                        else:
                            return False, "VRChat is rate-limiting boops right now. Please wait a bit and try again!"
                    else:
                        raise
                
                return True, "Emoji uploaded and boop sent successfully!"
            except Exception as e:
                log.error(f"Failed to upload emoji and boop: {e}")
                import traceback
                traceback.print_exc()
                return False, f"VRChat API error: {e}"

        return await asyncio.to_thread(_sync_task)

    def _cleanup_old_emojis(self):
        try:
            # We need to list files with tag 'emoji' and 'emojianimated'
            files = self.files_api.get_files(tag="emoji", n=100)
            animated_files = self.files_api.get_files(tag="emojianimated", n=100)
            
            all_emojis = files + animated_files
            
            if all_emojis:
                # The last item in the combined list will be an old emoji
                oldest_file = all_emojis[-1]
                log.info(f"Deleting old emoji file: {oldest_file.id}")
                self.files_api.delete_file(oldest_file.id)
                return True
        except Exception as e:
            log.error(f"Failed to cleanup old emojis: {e}")
        return False

# Global singleton
vrc_client = VRChatClient()
