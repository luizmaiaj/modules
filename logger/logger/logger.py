"""
Module to control logging to the streamlit interface
"""

from dataclasses import dataclass, field
import streamlit as st

@dataclass
class Logger:
    """
    Class to handle logging to a message container in Streamlit.
    """

    mc: st.container
    debug_mode: bool = field(default_factory=bool)

    def __init__(self, mc: st.container):
        """
        Initialize the Logger with a Streamlit message container.
        
        Parameters:
        mc (st.container): The Streamlit container for displaying messages.
        """
        self.debug_mode = False

        if 'messages' not in st.session_state:
            st.session_state['messages'] = []

        self.mc = mc

    def text(self, avatar, text):
        """
        Internal method to log a message with a specific avatar.
        
        Parameters:
        avatar (str): The avatar symbol to display next to the message.
        txt (str): The message to log.
        """
        with self.mc.chat_message(name='assistant', avatar=avatar):
            st.markdown(text)
        
        st.session_state.messages.append({'avatar': avatar, 'image': None, 'text': text})

    def text_stream(self, avatar, function, value) -> str:
        """
        Internal method to stream a message with a specific avatar.
        
        Parameters:
        avatar (str): The avatar symbol to display next to the message.
        text (str): The message to log.
        """
        text = ""
        with self.mc.chat_message(name='assistant', avatar=avatar):
            text = st.write_stream(function(value))

        st.session_state.messages.append({'avatar': avatar, 'image': None, 'text': text})

        return text

    def image(self, avatar, image, text):
        with self.mc.chat_message(name='assistant', avatar=avatar):
            st.image(image=image, caption=text)

        st.session_state.messages.append({'avatar': avatar, 'image': image, 'text': text})

    def set_level(self, debug_mode: bool):
        self.debug_mode = debug_mode

    def assistant(self, message):
        """
        Log an exception message.
        
        Parameters:
        message (str): The exception message to log.
        """
        self.text("🤖", message)

    def user(self, message):
        """
        Log an exception message.
        
        Parameters:
        message (str): The exception message to log.
        """
        self.text("😎", message)

    def critical(self, message):
        """
        Log an exception message.
        
        Parameters:
        message (str): The exception message to log.
        """
        self.text("🔥", message)

    def exception(self, message):
        """
        Log an exception message.
        
        Parameters:
        message (str): The exception message to log.
        """
        self.text("🐞", message)

    def error(self, message):
        """
        Log an error message.
        
        Parameters:
        message (str): The error message to log.
        """
        self.text("🚨", message)

    def warning(self, message):
        """
        Log a warning message.
        
        Parameters:
        message (str): The warning message to log.
        """
        self.text("⚠️", message)

    def success(self, message):
        """
        Log an exception message.
        
        Parameters:
        message (str): The exception message to log.
        """
        self.text("✅", message)

    def info(self, message):
        """
        Log an informational message.
        
        Parameters:
        message (str): The informational message to log.
        """
        self.text("ℹ️", message)

    def trace(self, message):
        """
        Log an exception message.
        
        Parameters:
        message (str): The exception message to log.
        """
        self.text("🔎", message)

    def debug(self, message):
        """
        Log a debug message.
        
        Parameters:
        message (str): The debug message to log.
        """
        if self.debug_mode:
            self.text("🔍", message)
