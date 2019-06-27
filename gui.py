import kivy
from functools import partial
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.properties import DictProperty
# maybe these should be withing the function that draws them?
# kivy properties will automatically set attributes for the class they are bound to (?), maybe that's the way it's supposed to work.
CURRENT_CONNECTIONS = {'project1': ['port', 'timeLeft'],
                       'project2': ['port', 'timeLeft'],}


SELECTED_JOBS = ''


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


class PopupTest(Popup):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(PopupTest, self).__init__(**kwargs)



########################################################################
class JobList(GridLayout):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        super(JobList, self).__init__(**kwargs)

        for i in CURRENT_CONNECTIONS:
            job = CURRENT_CONNECTIONS[i]
            but = Button()
            but.text = str(i + job[0] +job[1])
            if len(job) == 2:
                CURRENT_CONNECTIONS[i].append(but)

            but.bind(on_press = partial(self.selectStuff, i))  #
            self.add_widget(but)

    #----------------------------------------------------------------------
    def selectStuff(self, key, instance):
        """"""
        SELECTED_JOBS = key
        print(SELECTED_JOBS)
        instance.background_color = (0.5, 1, 0.2, 1)

        for i in CURRENT_CONNECTIONS:
            if i == key:
                continue
            btn = CURRENT_CONNECTIONS[i][2]
            btn.background_color = (1, 1, 1, 1)






#ROOT WIDGET
class RootWidget(BoxLayout):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
        """Constructor"""
        #initialize base window and set orientation
        super(RootWidget, self).__init__(**kwargs)

    #----------------------------------------------------------------------
    def changeProjects(*args):
        """"""
        CURRENT_CONNECTIONS['newproj'] = ['lalap', 'dereita']

    #----------------------------------------------------------------------
    def updateJobs(self, widget):
        """"""
        widget.do_layout()

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


