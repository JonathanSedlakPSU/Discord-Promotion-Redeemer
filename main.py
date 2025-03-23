#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import random
import time
import json

try:
    import httpx
    import colorama
    from pystyle import Center, Colorate, Colors
    from colorama import Fore, init
    from typing import Optional, Any
    import threading
    from itertools import cycle
    from base64 import b64encode as enc
    from timeit import default_timer as timer
    from datetime import timedelta
    init(autoreset=True)
    thread_lock = threading.Lock()
except Exception as e:
    print(e)

activated_accounts = 0

# Set console title and clear screen
os.system('title Discord Promo Checker')
os.system('cls' if os.name == 'nt' else 'clear')


class Console:
    """Console utilities for printing and updating terminal output."""

    @staticmethod
    def _time() -> str:
        """Return current time in HH:MM:SS format (GMT)."""
        return time.strftime("%H:%M:%S", time.gmtime())

    @staticmethod
    def clear() -> None:
        """Clear the terminal screen."""
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def sprint(content: str, status: bool = True) -> None:
        """
        Thread-safe print to stdout with a timestamp and colored status.
        
        Args:
            content (str): The content to print.
            status (bool, optional): Determines color (green for True, red for False).
        """
        thread_lock.acquire()
        sys.stdout.write(
            f"[{Fore.LIGHTBLUE_EX}{Console._time()}{Fore.RESET}] "
            f"{Fore.GREEN if status else Fore.RED}{content}\n{Fore.RESET}"
        )
        thread_lock.release()

    @staticmethod
    def update_title() -> None:
        """
        Continuously update the console title with activated account count and elapsed time.
        """
        start = timer()
        while True:
            thread_lock.acquire()
            end = timer()
            elapsed_time = timedelta(seconds=end - start)
            os.system(
                f"title Naito │ Activated Accounts: {activated_accounts} │ Elapsed: {elapsed_time}"
            )
            thread_lock.release()
            time.sleep(1)


class Others:
    """Utility class for miscellaneous operations."""

    @staticmethod
    def get_client_data() -> int:
        """
        Load client data (build number) from configuration.
        
        Returns:
            int: The build number.
        """
        with open("config.json", "r") as config_file:
            config = json.load(config_file)
        return config["build_num"]

    @staticmethod
    def remove_content(filename: str, delete_line: str) -> None:
        """
        Remove lines containing a specified string from a file.
        
        Args:
            filename (str): The path to the file.
            delete_line (str): The string to match for deletion.
        """
        thread_lock.acquire()
        with open(filename, "r+") as io:
            content = io.readlines()
            io.seek(0)
            for line in content:
                if delete_line not in line:
                    io.write(line)
            io.truncate()
        thread_lock.release()


class Redeemer:
    """
    Class to handle the redemption process using a payment method.
    
    This class handles session setup, Stripe interactions, and redeeming a Nitro gift.
    """

    def __init__(self, vcc: str, token: str, link: str, build_num: int, proxy: Optional[Any] = None) -> None:
        """
        Initialize the redeemer with payment info, token, link, build number, and optional proxy.
        
        Args:
            vcc (str): Card information in "number:expiry:ccv" format.
            token (str): Discord token.
            link (str): Promotion link.
            build_num (int): Build number from client data.
            proxy (Optional[Any], optional): Proxy settings. Defaults to None.
        """
        self.card_number, self.expiry, self.ccv = vcc.split(":")
        self.link = link
        self.token = token
        self.proxy = proxy
        self.build_num = build_num

        self.client = httpx.Client(proxies=proxy, timeout=90)
        self.stripe_client = httpx.Client(proxies=proxy, timeout=90)

        if "promos.discord.gg/" in self.link:
            self.link = f"https://discord.com/billing/promotions/{self.link.split('promos.discord.gg/')[1]}"

        if ":" in self.token:
            self.full_token = token
            self.token = token.split(":")[2]
        else:
            self.token = token

    def __tasks__(self) -> Any:
        """
        Execute all tasks required for redemption.
        
        Returns:
            Any: "auth" if authentication fails, or None if any step fails.
        """
        if not self.__session__():
            Console.sprint("Could not create a session", False)
            return

        if not self.__stripe():
            Console.sprint("Could not get stripe cookies", False)
            return

        if not self.__stripe_tokens():
            Console.sprint("Could not get confirm token", False)
            return

        if not self.setup_intents():
            Console.sprint("Could not setup intents [Client Secret]", False)
            return

        if not self.validate_billing():
            Console.sprint("Could not validate billing [Billing Token]", False)
            return

        if not self.__stripe_confirm():
            Console.sprint("Could not confirm stripe [Payment Id]", False)
            return

        if not self.add_payment():
            Console.sprint(f"Could not add vcc, error message: {self.error}", False)
            return

        redeem = self.redeem()
        if not redeem:
            Console.sprint(f"Could not redeem nitro, error: {self.error}", False)
            if "This payment method cannot be used" in self.error:
                Others.remove_content("data/vccs.txt", self.card_number)
            elif "Already purchased" in self.error:
                Others.remove_content("data/tokens.txt", self.token)
                with thread_lock:
                    with open("results/success.txt", "a") as success:
                        success.write(self.full_token + "\n" if hasattr(self, "full_token") else self.token + "\n")
            elif "This gift has been redeemed already" in self.error:
                Others.remove_content("data/promos.txt", self.link.split("/promotions/")[1])
            return
        elif redeem == "auth":
            return redeem
        else:
            Console.sprint(f"Redeemed Nitro -> {self.token}", True)
            Others.remove_content("data/tokens.txt", self.token)
            Others.remove_content("data/promos.txt", self.link.split("/promotions/")[1])
            with thread_lock:
                with open("results/success.txt", "a") as success:
                    success.write(self.full_token + "\n" if hasattr(self, "full_token") else self.token + "\n")
            global activated_accounts
            activated_accounts += 1

    def __session__(self) -> bool:
        """
        Setup the initial session with Discord.
        
        Returns:
            bool: True if session setup was successful, otherwise False.
        """
        self.client.headers.update({
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/104.0.5112.39 Safari/537.36"
            ),
            "sec-ch-ua": '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        })

        get_site = self.client.get(self.link)
        if get_site.status_code not in [200, 201, 204]:
            return False

        try:
            self.stripe_key = get_site.text.split("STRIPE_KEY: '")[1].split("',")[0]
            cookies = get_site.headers["set-cookie"]
            self.__dcfduid = cookies.split("__dcfduid=")[1].split(";")[0]
            self.__sdcfduid = cookies.split("__sdcfduid=")[1].split(";")[0]
        except Exception:
            return False

        self.client.cookies.update({
            "__dcfduid": self.__dcfduid,
            "__sdcfduid": self.__sdcfduid,
            "locale": "en-US",
        })

        # Set super properties for Discord client
        self.super_properties = enc(json.dumps({
            "os": "Windows",
            "browser": "Chrome",
            "device": "",
            "system_locale": "en-US",
            "browser_user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/104.0.5112.39 Safari/537.36"
            ),
            "browser_version": "104.0.5112.39",
            "os_version": "10",
            "referrer": "",
            "referring_domain": "",
            "referrer_current": "",
            "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": self.build_num,
            "client_event_source": None,
        }, separators=(",", ":")).encode()).decode("utf-8")

        self.client.headers.update({
            "X-Context-Properties": "eyJsb2NhdGlvbiI6IlJlZ2lzdGVyIn0=",
            "X-Debug-Options": "bugReporterEnabled",
            "X-Discord-Locale": "en-US",
            "X-Super-Properties": self.super_properties,
            "Host": "discord.com",
            "Referer": self.link,
            "Origin": "https://discord.com",
            "X-Fingerprint": None,  # Will be updated below
            "Authorization": self.token,
        })

        fingerprint_resp = self.client.get("https://discord.com/api/v9/experiments")
        if fingerprint_resp.status_code not in [200, 201, 204]:
            return False
        self.fingerprint = fingerprint_resp.json().get("fingerprint")
        self.client.headers["X-Fingerprint"] = self.fingerprint
        return True

    def __stripe(self) -> bool:
        """
        Set up Stripe by sending a request to get Stripe cookies.
        
        Returns:
            bool: True if successful, otherwise False.
        """
        self.stripe_client = httpx.Client(proxies=self.proxy, timeout=90)
        self.stripe_client.headers.update({
            "accept": "application/json",
            "accept-language": "en-CA,en;q=0.9",
            "content-type": "application/x-www-form-urlencoded",
            "dnt": "1",
            "origin": "https://m.stripe.network",
            "referer": "https://m.stripe.network/",
            "sec-ch-ua": '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/104.0.5112.39 Safari/537.36"
            ),
        })

        response = self.stripe_client.post("https://m.stripe.com/6",
                                           data="JTdCJTIydjIlMjIlM0EyJTJDJTIyaWQlMjIlM0ElMjIwYWQ5NTYwYzZkYjIxZDRhZTU3ZGM5NmQ0ZThlZGY3OCUyMiUyQyUyMnQlMjIlM0EyNC45JTJDJTIydGFnJTIyJTNBJTIyNC41LjQyJTIyJTJDJTIyc3JjJTIyJTNBJTIyanMlMjIlMkMlMjJhJTIyJTNBJTdCJTIyYSUyMiUzQSU3QiUyMnYlMjIlM0ElMjJmYWxzZSUyMiUyQyUyMnQlMjIlM0EwLjIlN0QlMkMlMjJiJTIyJTNBJTdCJTIydiUyMiUzQSUyMnRydWUlMjIlMkMlMjJ0JTIyJTNBMCU3RCUyQyUyMmMlMjIlM0ElN0IlMjJ2JTIyJTNBJTIyZW4tQ0ElMjIlMkMlMjJ0JTIyJTNBMCU3RCUyQyUyMmQlMjIlM0ElN0IlMjJ2JTIyJTNBJTIyV2luMzIlMjIlMkMlMjJ0JTIyJTNBMCU3RCUyQyUyMmUlMjIlM0ElN0IlMjJ2JTIyJTNBJTIyUERGJTIwVmlld2VyJTJDaW50ZXJuYWwtcGRmLXZpZXdlciUyQ2FwcGxpY2F0aW9uJTJGcGRmJTJDcGRmJTJCJTJCdGV4dCUyRnBkZiUyQ3BkZiUyQyUyMENocm9tZSUyMFBERiUyMFZpZXdlciUyQ2ludGVybmFsLXBkZi12aWV3ZXIlMkNhcHBsaWNhdGlvbiUyRnBkZiUyQ3BkZiUyQiUyQnRleHQlMkZwZGYlMkNwZGYlMkMlMjBDaHJvbWl1bSUyMFBERiUyMFZpZXdlciUyQ2ludGVybmFsLXBkZi12aWV3ZXIlMkNhcHBsaWNhdGlvbiUyRnBkZiUyQ3BkZiUyQiUyQnRleHQlMkZwZGYlMkNwZGYlMkMlMjBNaWNyb3NvZnQlMjBFZGdlJTIwUERGJTIwVmlld2VyJTJDaW50ZXJuYWwtcGRmLXZpZXdlciUyQ2FwcGxpY2F0aW9uJTJGcGRmJTJDcGRmJTJCJTJCdGV4dCUyRnBkZiUyQ3BkZiUyMiUyQyUyMnQlMjIlM0EwJTdEJTJDJTIyZyUyMiUzQSU3QiUyMnYlMjIlM0ElMjItNCUyMiUyQyUyMnQlMjIlM0EwJTdEJTJDJTIyaCUyMiUzQSU3QiUyMnYlMjIlM0ElMjJmYWxzZSUyMiUyQyUyMnQlMjIlM0EwJTdEJTJDJTIyaSUyMiUzQSU3QiUyMnYlMjIlM0ElMjJzZXNzaW9uU3RvcmFnZS1kaXNhYmxlZCUyQyUyMGxvY2FsU3RvcmFnZS1kaXNhYmxlZCUyMiUyQyUyMnQlMjIlM0EwLjElN0QlMkMlMjJqJTIyJTNBJTdCJTIydiUyMiUzQSUyMjAxMDAxMDAxMDExMTExMTExMDAxMTExMDExMTExMTExMDExMTAwMTAxMTAxMTExMTAxMTExMTElMjIlMkMlMjJ0JTIyJTNBOS4yJTJDJTIyYXQlMjIlM0ElMjJmJTIyJTNBJTdCJTIydiUyMiUzQSUyMjE5MjB3XzEwNDBoXzI0ZF8xciUyMiUyQyUyMnQlMjIlM0EwJTdEJTJDJTIybCUyMiUzQSU3QiUyMnYlMjIlM0ElMjJNb3ppbGxhJTJGNS4wJTIwKFdpbmRvd3MlMjBOVCUyMDEwLjAlM0IlMjBXT1c2NCklMjBBcHBsZVdlYktpdCUyRjUzNy4zNiUyRChLSFRNTCUyQyUyMGxpa2UlMjBHZWNrbyklMjBDaHJvbWUlMkYxMDMuMC4wLjAlMjBTYWZhcmklMkY1MzcuMzYlMkMlMjJ0JTIyJTNBMCU3RCUyQyUyMm0lMjIlM0ElN0IlMjJ2JTIyJTNBJTIyJTIyJTJDJTIydCUyMiUzQTAlN0QlMkMlMjJuJTIyJTNBJTdCJTIydiUyMiUzQSUyMmZhbHNlJTIyJTJDJTIydCUyMiUzQTIxLjUlMkMlMjJhdCUyMiUzQTAuMiU3RCUyQyUyMm8lMjIlM0ElN0IlMjJ2JTIyJTNBJTIyMTZlNzljMzY0YjkwNDM0NGU1ODFmNjlhMTI4ZTNkYTglMjIlMkMlMjJ0JTIyJTNBMCU3RCUyQyUyMmUlMjIlM0ElMjJ2JTIyJTNBJTIyUERGJTIwVmlld2VyJTJDaW50ZXJuYWwtcGRmLXZpZXdlciUyQ2FwcGxpY2F0aW9uJTJGcGRmJTJDcGRmJTJCJTJCdGV4dCUyRnBkZiUyQ3BkZiUyMiUyQyUyMnQlMjIlM0ElMjJfSWwxX2c2VDlzcjVXcS10eUhkZUwxZWVFdHo3TzdJRE8xZ3JDLU5aY1VrJTIyJTJDJTIyZCUyMiUzQSUyMjBiOTYwMGE5LTkyNjctNGViNi05NGNhLTM1MzNhMDE4NGExMTQxMDc3NiUyMiUyQyUyMmUlMjIlM0ElMjJmOGFkN2Y2Ny1lMWFmLTQxZTctYjlmMy1kNzRjZGRlMGI1NGQzZThiODAlMjIlMkMlMjJmJTIyJTNBZmFsc2UlMkMlMjJnJTIyJTNBdHJ1ZSUyQyUyMmglMjIlM0F0cnVlJTJDJTIyaSUyMiUzQSU1QiUyMmxvY2F0aW9uJTIyJTVEJTJDJTIyaiUyMiUzQSU1QiU1RCUyQyUyMm4lMjIlM0EyNjcuNSUyQyUyMnUlMjIlM0ElMjJkaXNjb3JkLmNvbSUyMiUyQyUyMnYlMjIlM0ElMjJkaXNjb3JkLmNvbSUyMiU3RCUyQyUyMmglMjIlM0ElMjI5NjI5ZjFjZWM1NGY1YjhmM2IxYSUyMiU3RA=="
        )

        response = self.stripe_client.post("https://m.stripe.com/6", data="dummy")
        if response.status_code not in [200, 201, 204]:
            return False

        # Extract identifiers from Stripe fingerprint response
        try:
            self.muid = response.json()["muid"]
            self.guid = response.json()["guid"]
            self.sid = response.json()["sid"]
        except Exception:
            return False

        self.client.cookies.update({"__stripe_mid": self.muid, "__stripe_sid": self.sid})
        return True

    def __stripe_tokens(self) -> bool:
        """
        Request Stripe token for the provided card information.
        
        Returns:
            bool: True if token retrieval was successful, otherwise False.
        """
        data = (
            f"card[number]={self.card_number}&card[cvc]={self.ccv}"
            f"&card[exp_month]={self.expiry[:2]}&card[exp_year]={self.expiry[-2:]}"
            f"&guid={self.guid}&muid={self.muid}&sid={self.sid}"
            f"&payment_user_agent=stripe.js%2Ff0346bf10%3B+stripe-js-v3%2Ff0346bf10"
            f"&time_on_page={random.randint(60000, 120000)}&key={self.stripe_key}"
            f"&pasted_fields=number%2Cexp%2Ccvc"
        )
        response = self.stripe_client.post("https://api.stripe.com/v1/tokens", data=data)
        if response.status_code == 200:
            self.confirm_token = response.json()["id"]
            return True
        return False

    def setup_intents(self) -> bool:
        """
        Setup billing intents with Discord.
        
        Returns:
            bool: True if successful, otherwise False.
        """
        response = self.client.post("https://discord.com/api/v9/users/@me/billing/stripe/setup-intents")
        if response.status_code == 200:
            self.client_secret = response.json()["client_secret"]
            return True
        return False

    def validate_billing(
        self,
        name: str = "John Wick",
        line_1: str = "27 Oakland Pl",
        line_2: str = "",
        city: str = "Brooklyn",
        state: str = "NY",
        postal_code: str = "11226",
        country: str = "US",
        email: str = "",
    ) -> bool:
        """
        Validate billing information with Discord.
        
        Args:
            name (str): Cardholder name.
            line_1 (str): Address line 1.
            line_2 (str): Address line 2.
            city (str): City.
            state (str): State.
            postal_code (str): ZIP code.
            country (str): Country code.
            email (str): Email address.
        
        Returns:
            bool: True if billing is validated, otherwise False.
        """
        response = self.client.post(
            "https://discord.com/api/v9/users/@me/billing/payment-sources/validate-billing-address",
            json={
                "billing_address": {
                    "name": name,
                    "line_1": line_1,
                    "line_2": line_2,
                    "city": city,
                    "state": state,
                    "postal_code": postal_code,
                    "country": country,
                    "email": email,
                }
            },
        )
        if response.status_code == 200:
            self.billing_token = response.json()["token"]
            return True
        return False

    @staticmethod
    def parse_data(content: str) -> str:
        """
        Prepare data for URL encoding by replacing spaces.
        
        Args:
            content (str): The text to parse.
        
        Returns:
            str: The parsed content.
        """
        return content.replace(" ", "+")

    def __stripe_confirm(self) -> bool:
        """
        Confirm the Stripe payment using billing details.
        
        Returns:
            bool: True if confirmation succeeded, otherwise False.
        """
        self.depracted_client_secret = str(self.client_secret).split("_secret_")[0]
        data = (
            f"payment_method_data[type]=card&"
            f"payment_method_data[card][token]={self.confirm_token}&"
            f"payment_method_data[billing_details][address][line1]={self.parse_data(self.line_1)}&"
            f"payment_method_data[billing_details][address][line2]={self.parse_data(self.line_2) if self.line_2 else ''}&"
            f"payment_method_data[billing_details][address][city]={self.city}&"
            f"payment_method_data[billing_details][address][state]={self.state}&"
            f"payment_method_data[billing_details][address][postal_code]={self.postal_code}&"
            f"payment_method_data[billing_details][address][country]={self.country}&"
            f"payment_method_data[billing_details][name]={self.parse_data(self.name)}&"
            f"payment_method_data[guid]={self.guid}&"
            f"payment_method_data[muid]={self.muid}&"
            f"payment_method_data[sid]={self.sid}&"
            f"payment_method_data[payment_user_agent]=stripe.js%2Ff0346bf10%3B+stripe-js-v3%2Ff0346bf10&"
            f"payment_method_data[time_on_page]={random.randint(210000, 450000)}&"
            f"expected_payment_method_type=card&use_stripe_sdk=true&key={self.stripe_key}&client_secret={self.client_secret}"
        )
        response = self.stripe_client.post(
            f"https://api.stripe.com/v1/setup_intents/{self.depracted_client_secret}/confirm", data=data
        )
        if response.status_code == 200:
            self.payment_id = response.json()["payment_method"]
            return True
        return False

    def add_payment(self) -> bool:
        """
        Add the payment method to Discord billing.
        
        Returns:
            bool: True if the payment method was added successfully, otherwise False.
        """
        payload = {
            "payment_gateway": 1,
            "token": self.payment_id,
            "billing_address": {
                "name": self.name,
                "line_1": self.line_1,
                "line_2": self.line_2,
                "city": self.city,
                "state": self.state,
                "postal_code": self.postal_code,
                "country": self.country,
                "email": self.email,
            },
            "billing_address_token": self.billing_token,
        }
        response = self.client.post(
            "https://discord.com/api/v9/users/@me/billing/payment-sources", json=payload
        )
        if response.status_code == 200:
            self.payment_source_id = response.json()["id"]
            return True
        else:
            self.error = response.json()["errors"]["_errors"][0]["message"]
            return False

    def redeem(self) -> Any:
        """
        Redeem the Discord promotion.
        
        Returns:
            Any: True if redeemed successfully, "auth" if authentication is required, or False on error.
        """
        promo_code = self.link.split("https://discord.com/billing/promotions/")[1]
        response = self.client.post(
            f"https://discord.com/api/v9/entitlements/gift-codes/{promo_code}/redeem",
            json={"channel_id": None, "payment_source_id": self.payment_source_id},
        )
        if response.status_code == 200:
            return True
        elif response.json().get("message") == "Authentication required":
            self.stripe_payment_id = response.json()["payment_id"]
            return "auth"
        else:
            self.error = response.json().get("message", "Unknown error")
            return False


class Authentication(Redeemer):
    """
    Authentication class for handling the complex Nitro redemption workflow.
    
    Inherits from Redeemer and adds additional methods for payment intent
    confirmation, fingerprinting, and authentication.
    """

    def __init__(
        self,
        vcc: str,
        token: str,
        link: str,
        build_num: int = Others.get_client_data(),
        proxy: Optional[Any] = None,
    ) -> None:
        super().__init__(vcc, token, link, build_num, proxy)
        try:
            if self.__tasks__() == "auth":
                if not self.discord_payment_intents():
                    Console.sprint("Could not setup discord payment intents", False)
                    return

                time.sleep(0.2)
                if not self.stripe_payment_intents():
                    Console.sprint("Could not setup stripe payment intents [1]", False)
                    return

                time.sleep(0.2)
                if not self.stripe_payment_intents_2():
                    Console.sprint("Could not setup stripe payment intents [2]", False)
                    return

                time.sleep(0.2)
                if not self.stripe_fingerprint():
                    Console.sprint("Could not send fingerprint to stripe", False)
                    return

                time.sleep(0.2)
                if not self.authenticate():
                    Console.sprint("Could not authenticate vcc", False)
                    return

                time.sleep(0.2)
                if not self.billing():
                    Console.sprint("Could not validate billing", False)
                    return

                time.sleep(0.2)
                redeem = self.redeem()
                if not redeem:
                    Console.sprint(f"Could not redeem nitro, error: {self.error}", False)
                    if "This payment method cannot be used" in self.error:
                        Others.remove_content("data/vccs.txt", self.card_number)
                    return
                elif redeem == "auth":
                    Console.sprint("Could not authenticate vcc", False)
                    return
                else:
                    Console.sprint(f"Redeemed Nitro -> {self.token}", True)
                    Others.remove_content("data/tokens.txt", self.token)
                    Others.remove_content("data/promos.txt", self.link.split("/promotions/")[1])
                    with thread_lock:
                        with open("results/success.txt", "a") as success:
                            success.write(self.full_token + "\n" if hasattr(self, "full_token") else self.token + "\n")
                    global activated_accounts
                    activated_accounts += 1
            else:
                return
        except Exception as err:
            Console.sprint(f"An error occurred: {err}", False)

    def discord_payment_intents(self) -> bool:
        """
        Retrieve Discord payment intent details.
        
        Returns:
            bool: True if successful, otherwise False.
        """
        response = self.client.get(
            f"https://discord.com/api/v9/users/@me/billing/stripe/payment-intents/payments/{self.stripe_payment_id}"
        )
        if response.status_code == 200:
            data = response.json()
            self.stripe_payment_intent_client_secret = data.get("stripe_payment_intent_client_secret")
            self.depracted_stripe_payment_intent_client_secret = str(
                self.stripe_payment_intent_client_secret
            ).split("_secret_")[0]
            self.stripe_payment_intent_payment_method_id = data.get("stripe_payment_intent_payment_method_id")
            return True
        return False

    def stripe_payment_intents(self) -> bool:
        """
        Confirm the Stripe payment intent details.
        
        Returns:
            bool: True if confirmed, otherwise False.
        """
        url = f"https://api.stripe.com/v1/payment_intents/{self.depracted_stripe_payment_intent_client_secret}"
        params = {
            "key": self.stripe_key,
            "is_stripe_sdk": "false",
            "client_secret": self.stripe_payment_intent_client_secret,
        }
        response = self.stripe_client.get(url, params=params)
        return response.status_code == 200

    def stripe_payment_intents_2(self) -> bool:
        """
        Confirm the Stripe payment intent via a second request.
        
        Returns:
            bool: True if successful, otherwise False.
        """
        data = {
            "expected_payment_method_type": "card",
            "use_stripe_sdk": "true",
            "key": self.stripe_key,
            "client_secret": self.stripe_payment_intent_client_secret,
        }
        url = f"https://api.stripe.com/v1/payment_intents/{self.depracted_stripe_payment_intent_client_secret}/confirm"
        response = self.stripe_client.post(url, data=data)
        if response.status_code == 200:
            next_action = response.json().get("next_action", {}).get("use_stripe_sdk", {})
            self.server_transaction_id = next_action.get("server_transaction_id")
            self.three_d_secure_2_source = next_action.get("three_d_secure_2_source")
            self.merchant = next_action.get("merchant")
            self.three_ds_method_url = next_action.get("three_ds_method_url")
            return True
        return False

    def stripe_fingerprint(self) -> bool:
        """
        Send a fingerprint to Stripe for 3D Secure verification.
        
        Returns:
            bool: True if successful, otherwise False.
        """
        self.threeDSMethodNotificationURL = f"https://hooks.stripe.com/3d_secure_2/fingerprint/{self.merchant}/{self.three_d_secure_2_source}"
        data = {
            "threeDSMethodData": enc(
                json.dumps({"threeDSServerTransID": self.server_transaction_id}, separators=(",", ":")).encode()
            ).decode("utf-8")
        }
        response = self.stripe_client.post(self.threeDSMethodNotificationURL, data=data)
        return response.status_code == 200

    def authenticate(self) -> bool:
        """
        Authenticate the card using 3DS2.
        
        Returns:
            bool: True if authentication succeeds, otherwise False.
        """
        data = (
            f"source={self.three_d_secure_2_source}&browser="
            f"%7B%22fingerprintAttempted%22%3Atrue%2C%22fingerprintData%22%3A%22"
            f"{enc(json.dumps({'threeDSServerTransID': self.server_transaction_id}, separators=(',', ':')).encode()).decode('utf-8')}"
            f"%22%2C%22challengeWindowSize%22%3Anull%2C%22threeDSCompInd%22%3A%22Y%22%2C"
            f"%22browserJavaEnabled%22%3Afalse%2C%22browserJavascriptEnabled%22%3Atrue%2C"
            f"%22browserLanguage%22%3A%22en-US%22%2C%22browserColorDepth%22%3A%2224%22%2C"
            f"%22browserScreenHeight%22%3A%221080%22%2C%22browserScreenWidth%22%3A%221920%22%2C"
            f"%22browserTZ%22%3A%22240%22%2C%22browserUserAgent%22%3A%22Mozilla%2F5.0+"
            f"(Windows+NT+10.0%3B+Win64%3B+x64)+AppleWebKit%2F537.36+(KHTML%2C+like+Gecko)+"
            f"Chrome%2F104.0.5112.39+Safari%2F537.36%22%7D"
            f"&one_click_authn_device_support[hosted]=false"
            f"&one_click_authn_device_support[same_origin_frame]=false"
            f"&one_click_authn_device_support[spc_eligible]=true"
            f"&one_click_authn_device_support[webauthn_eligible]=true"
            f"&one_click_authn_device_support[publickey_credentials_get_allowed]=true"
            f"&key={self.stripe_key}"
        )
        response = self.stripe_client.post("https://api.stripe.com/v1/3ds2/authenticate", data=data)
        return response.status_code == 200

    def billing(self) -> bool:
        """
        Validate billing by checking payment details.
        
        Returns:
            bool: True if billing is valid, otherwise False.
        """
        response = self.client.get(
            f"https://discord.com/api/v9/users/@me/billing/payments/{self.stripe_payment_id}"
        )
        return response.status_code == 200

    def redeem(self) -> Any:
        """
        Redeem the Nitro promotion.
        
        Returns:
            bool or str: True if redeemed successfully, "auth" if authentication is required, or False on failure.
        """
        promo_code = self.link.split("https://discord.com/billing/promotions/")[1]
        response = self.client.post(
            f"https://discord.com/api/v9/entitlements/gift-codes/{promo_code}/redeem",
            json={"channel_id": None, "payment_source_id": self.payment_source_id},
        )
        if response.status_code == 200:
            return True
        elif response.json().get("message") == "Authentication required":
            self.stripe_payment_id = response.json().get("payment_id")
            return "auth"
        else:
            self.error = response.json().get("message", "Unknown error")
            return False


# Main execution loop
if __name__ == "__main__":
    if not os.getenv('requirements'):
        subprocess.Popen(['start', 'start.bat'], shell=True)
        sys.exit()

    os.system('cls' if os.name == 'nt' else 'clear')
    Console.clear()

    # Deinitialize colorama for raw output
    colorama.deinit()
    print(
        Center.XCenter(
            Colorate.Vertical(
                Colors.blue_to_purple,
                f"""
    ____           __                             
   / __ \___  ____/ /__  ___  ____ ___  ___  _____
  / /_/ / _ \/ __  / _ \/ _ \/ __ `__ \/ _ \/ ___/
 / _, _/  __/ /_/ /  __/  __/ / / / / /  __/ /    
/_/ |_|\___/\__,_/\___/\___/_/ /_/ /_/\___/_/     
"""
            )
        )
    )
    colorama.init(autoreset=True)

    # Load configuration and resources
    with open("config.json", "r") as config_file:
        config_data = json.load(config_file)

    proxies = cycle(open("data/proxies.txt", "r").read().splitlines())
    vccs = open("data/vccs.txt", "r").read().splitlines()
    tokens = open("data/tokens.txt", "r").read().splitlines()
    promolinks = open("data/promos.txt", "r").read().splitlines()
    use_on_cc = config_data["use_on_vcc"]
    thread_count = config_data["threads"]
    build_num = Others.get_client_data()

    # Duplicate VCC entries based on usage configuration
    duplicate_vccs = []
    for vcc in vccs:
        for _ in range(use_on_cc):
            duplicate_vccs.append(vcc)

    # Main processing loop
    while len(vccs) and len(tokens) and len(promolinks) > 0:
        try:
            local_threads = []
            for _ in range(thread_count):
                try:
                    next_proxy = "http://" + next(proxies)
                    proxy = {"http://": next_proxy, "https://": next_proxy}
                except StopIteration:
                    proxy = None

                token = tokens[0]
                vcc = duplicate_vccs[0]
                link = promolinks[0]

                start_thread = threading.Thread(
                    target=Authentication,
                    args=(vcc, token, link, build_num, proxy),
                )
                local_threads.append(start_thread)
                start_thread.start()

                # Remove used items
                tokens.pop(0)
                promolinks.pop(0)
                duplicate_vccs.pop(0)
                if vcc not in duplicate_vccs:
                    Others.remove_content("data/vccs.txt", vcc)

            for thread in local_threads:
                thread.join()

        except IndexError:
            break
        except Exception:
            pass

        Console.sprint("Ran out of materials, Threads may have not finished yet", False)
