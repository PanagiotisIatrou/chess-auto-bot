import re

from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from grabbers.grabber import Grabber


class LichessGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)

    def update_board_elem(self):
        try:
            # Try finding the normal board
            self._board_elem = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/div[1]/div/cg-container')
        except NoSuchElementException:
            try:
                # Try finding the board in the puzzles page
                self._board_elem = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[1]/div/cg-container')
            except NoSuchElementException:
                self._board_elem = None

    def is_white(self):
        # Get "ranks" child
        children = self._board_elem.find_elements(By.XPATH, "./*")
        child = [x for x in children if "ranks" in x.get_attribute("class")][0]
        if child.get_attribute("class") == "ranks":
            return True
        else:
            return False

    def is_game_over(self):
        try:
            # Find the game over window
            self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/aside/div/section[2]')

            # If we don't have an exception at this point, we have found the game over window
            return True
        except NoSuchElementException:
            # Try finding the puzzles game over window and checking its class
            try:
                # The game over window
                game_over_window = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[3]/div[1]')

                if game_over_window.get_attribute("class") == "complete":
                    return True

                # If we don't have an exception at this point and the window's class is not "complete",
                # then the game is still going
                return False
            except NoSuchElementException:
                return False

    def get_move_list(self):
        puzzles = self.is_game_puzzles()

        if puzzles:
            try:
                # Try finding the move list in the puzzles page
                move_list_elem = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[2]/div')
            except NoSuchElementException:
                return None
        else:
            try:
                # Try finding the normal move list
                move_list_elem = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/rm6/l4x')
            except NoSuchElementException:
                try:
                    # Try finding the normal move list when there are no moves yet
                    self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/rm6')

                    # If we don't have an exception at this point, we don't have any moves yet
                    return []
                except NoSuchElementException:
                    return None

        try:
            if not puzzles:
                children = move_list_elem.find_elements(By.TAG_NAME, "xau")
            else:
                children = move_list_elem.find_elements(By.TAG_NAME, "move")
        except NoSuchElementException:
            return None

        # Get the moves from the lines
        moves_list = []
        for move in children:
            # Sanitize the move
            move = re.sub(r"[^a-zA-Z0-9+-]", "", move.text)
            moves_list.append(move)
        return moves_list

    def is_game_puzzles(self):
        try:
            # Try finding the puzzles text
            self.chrome.find_element(By.XPATH, "/html/body/div[2]/main/aside/div[1]/div[1]/div/p[1]")

            # If we don't have an exception at this point, the game is a puzzle
            return True
        except NoSuchElementException:
            return False

    def click_puzzle_next(self):
        # Find the next continue training button
        try:
            next_button = self.chrome.find_element(By.XPATH, "/html/body/div[2]/main/div[2]/div[3]/a")
        except NoSuchElementException:
            try:
                next_button = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[2]/div[3]/div[3]/a[2]')
            except NoSuchElementException:
                return

        # Click the continue training button
        self.chrome.execute_script("arguments[0].click();", next_button)

    def ws_execute_move(self, move):
        message = '{"t":"move","d":{"u":"' + move + '","b":1,"a":' + str(move_count) + '}}'
        script = 'lichess.socket.ws.send(JSON.stringify(' + message + '))'
        self.chrome.execute_script(script)