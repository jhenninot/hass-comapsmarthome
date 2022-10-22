from http.client import HTTPException
import httpx
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)

class ComapClient(object):
    token = ""
    _BASEURL = "https://api.comapsmarthome.com/"

    def __init__(self,username,password,clientid="56jcvrtejpracljtirq7qnob44"):
        _USERNAME = username
        _PASSWORD = password
        _CLIENT_ID = "56jcvrtejpracljtirq7qnob44"
        _REGION_NAME = "eu-west-3"
        url = "https://cognito-idp.eu-west-3.amazonaws.com"
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
            "origin": "https://app.comapsmarthome.com",
            "referer": "https://app.comapsmarthome.com",
        }
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {
                "USERNAME": username,
                "PASSWORD": password,
            },
            "ClientId": "56jcvrtejpracljtirq7qnob44",
        }

        try:
            login_request = httpx.post(url, json=payload, headers=headers)
            login_request.raise_for_status()
            response = login_request.json()
            self.lastRequest = datetime.now()
            self.token = response.get("AuthenticationResult").get("AccessToken")
            self.refreshToken = response.get("AuthenticationResult").get("RefreshToken")
            self.tokenExpires = response.get("AuthenticationResult").get("ExpiresIn")
            housings = self.get_housings()
            self.housing = housings[0].get("id")
        except httpx.HTTPStatusError as err:
            _LOGGER.error('Could not set up COMAP client - %s status code. Check your credentials',err.response.status_code)
            raise ComapClientException("Client set up failed",err.response.status_code) from err

    def get_request(self, url, headers=None, params={}):
        if (datetime.now() - self.lastRequest).total_seconds() > (
            self.tokenExpires - 60
        ):
            self.refresh_token()
        if headers is None:
            headers = {
                "Authorization": "Bearer {}".format(self.token),
                "Content-Type": "application/json",
            }
        r = httpx.get(url=url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()

    async def async_post(self, url, headers=None, json={}):
        if (datetime.now() - self.lastRequest).total_seconds() > (
            self.tokenExpires - 60
        ):
            self.refresh_token()
        if headers is None:
            headers = {
                "Authorization": "Bearer {}".format(self.token),
                "Content-Type": "application/json",
            }
        async with httpx.AsyncClient() as client:
            r = await client.post(url=url, headers=headers, json=json)
            r.raise_for_status()
            return r.json()

    async def async_get(self, url, headers=None, params={}):
        if (datetime.now() - self.lastRequest).total_seconds() > (
            self.tokenExpires - 60
        ):
            self.refresh_token()
        if headers is None:
            headers = {
                "Authorization": "Bearer {}".format(self.token),
                "Content-Type": "application/json",
            }
        async with httpx.AsyncClient() as client:
            r = await client.get(url=url, headers=headers, params=params)
            return r.json()

    async def async_delete(self, url, headers=None):
        if (datetime.now() - self.lastRequest).total_seconds() > (
            self.tokenExpires - 60
        ):
            self.refresh_token()
        if headers is None:
            headers = {
                "Authorization": "Bearer {}".format(self.token),
                "Content-Type": "application/json",
            }
        async with httpx.AsyncClient() as client:
            r = await client.delete(url=url, headers=headers)
            return r.json()

    def refresh_token(self):
        url = "https://cognito-idp.eu-west-3.amazonaws.com"
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
            "origin": "https://app.comapsmarthome.com",
            "referer": "https://app.comapsmarthome.com",
        }
        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "AuthParameters": {"REFRESH_TOKEN": self.refreshToken},
            "ClientId": "4s41oamtn4655ft1csnm9tjonb",
        }

        login_request = httpx.post(url, json=payload, headers=headers)
        response = login_request.json()
        self.lastRequest = datetime.now()
        self.token = response.get("AuthenticationResult").get("AccessToken")
        self.tokenExpires = response.get("AuthenticationResult").get("ExpiresIn")

    def get_housings(self):
        return self.get_request(self._BASEURL + "park/housings")

    def get_zones(self, housing=None):
        if housing is None:
            housing = self.housing
        return self.get_request(
            self._BASEURL + "thermal/housings/" + housing + "/thermal-details"
        )

    def get_zone(self, zoneid, housing=None):
        if housing is None:
            housing = self.housing
        return self.get_request(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-details/zones/"
            + zoneid
        )

    async def leave_home(self, housing=None):
        if housing is None:
            housing = self.housing
        return await self.async_post(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-control/leave-home"
        )

    async def return_home(self, housing=None):
        """THis is used to cancel a leave home signal"""
        if housing is None:
            housing = self.housing
        return await self.async_delete(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-control/leave-home"
        )

    async def away_return(self, housing=None):
        """This is used to cancel a programmed away mode."""
        if housing is None:
            housing = self.housing
        return await self.async_post(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/thermal-control/come-back-home"
        )

    async def get_schedules(self, housing=None):
        """This returns a list of schedules available for a housing."""
        if housing is None:
            housing = self.housing
        return await self.async_get(
            self._BASEURL + "thermal/housings/" + housing + "/schedules"
        )
    
    async def get_custom_temperatures(self, housing=None):
        """This returns the temperatures corresponding to instructions for different zones."""
        if housing is None:
            housing = self.housing
        return await self.async_get(
            self._BASEURL + "thermal/housings/" + housing + "/custom-temperatures"
        )


    async def get_programs(self, housing=None):
        """This returns the active program and list of schedules for a housing."""
        if housing is None:
            housing = self.housing
        return await self.async_get(
            self._BASEURL + "thermal/housings/" + housing + "/programs"
        )

    async def get_active_schedules(self, housing=None):
        """Returns an array of zones with their active schedules"""
        programs = await self.get_programs(housing)
        active_schedules = []
        try:
            for program in programs['programs']:
                if program['is_activated']:
                    active_schedules = program['zones']
        except AttributeError:
            _LOGGER.error('Could not find active program for Comap housing')
            
        return active_schedules


    async def set_schedule(
        self, zone, schedule_id, program_id=None, program_mode="connected", housing=None
    ):
        if housing is None:
            housing = self.housing
        if program_id is None:
            # get the current active program
            programs = await self.get_programs(housing)
            for program in programs["programs"]:
                if program["is_activated"] is True:
                    program_id = program["id"]
                    break
        data = {"schedule_id": schedule_id, "programming_type": program_mode}
        return await self.async_post(
            self._BASEURL
            + "thermal/housings/"
            + housing
            + "/programs/"
            + program_id
            + "/zones/"
            + zone,
            json=data,
        )
    
    async def set_temporary_instruction(self, zone, instruction, duration=120, housing=None):
        '''Set a temporary instruction for a zone, for a given duration in minutes'''
        if housing is None:
            housing = self.housing
        data = {"duration": duration, "set_point": {"instruction": instruction}}

        try:
            r = await self.async_post(
                self._BASEURL
                + "thermal/housings/"
                + housing
                + "/thermal-control/zones/"
                + zone
                + "/temporary-instruction",
                json=data,
            )        
            return r
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 409:
                await self.remove_temporary_instruction(zone,housing)
                return await self.set_temporary_instruction(zone,instruction,duration=duration,housing=housing)
            else:
                raise err
        

    async def remove_temporary_instruction(self, zone, housing=None):
        '''Set a temporary instruction for a zone, for a given duration in minutes'''
        if housing is None:
            housing = self.housing

        try:
            r = await self.async_delete(
                self._BASEURL
                + "thermal/housings/"
                + housing
                + "/thermal-control/zones/"
                + zone
                + "/temporary-instruction",
            )        
            return r
        except httpx.HTTPStatusError as err:
            _LOGGER.error(err)

class ComapClientException(Exception):
    """Exception with ComapSmartHome client."""

class ComapClientAuthException(Exception):
    """Exception with ComapSmartHome client."""