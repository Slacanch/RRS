import kivy
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup

# CURRENT CONNECTION CLASSES
########################################################################
class CurrentConnection(Label):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(CurrentConnection, self).__init__(**kwargs)
        pass


# BUTTON GRID CLASSES
########################################################################
class ButtonGrid(GridLayout):
    """add to mid layer buttons"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(ButtonGrid, self).__init__(**kwargs)
        # self.cols = 4

        # self.add_widget(Connect())
        # self.add_widget(Connect())
        # self.add_widget(Connect())
        # self.add_widget(Connect())


class Connect(Button):
    """add actual buttons"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""

        super(Connect, self).__init__(**kwargs)
        self.background_color = 'red'
        self.text = 'Connect to Server'

# CURRENT JOBS CLASSES
########################################################################
class CurrentJobs(Label):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(CurrentJobs, self).__init__(**kwargs)
        pass

# LOG OUTPUT CLASSES
########################################################################
class LogOutput(Label):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(LogOutput, self).__init__(**kwargs)
        pass


# SPLASH SCREEN CLASSES
#########################################################################
class SplashScreen():
    """show while initializing connections"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""


########################################################################
class PopupTest(Popup):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(PopupTest, self).__init__(**kwargs)


#ROOT WIDGET
########################################################################
class RootWidget(BoxLayout):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        #initialize base window and set orientation
        super(RootWidget, self).__init__(**kwargs)




#########################################################################
class GuiApp(App):
    """"""

    #----------------------------------------------------------------------
    def build(self):
        """Constructor"""
        self.title = 'Single Cell Project Manager V0.01'
        return RootWidget()




if __name__ == '__main__':
    GuiApp().run()


