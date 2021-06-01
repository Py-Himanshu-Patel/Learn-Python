# computer.py
class Computer:

    def display(self):
        print('Custom Computer:')
        print('\t{:>10}: {}'.format('Case', self.case))
        print('\t{:>10}: {}'.format('Mainboard', self.mainboard))
        print('\t{:>10}: {}'.format('CPU', self.cpu))
        print('\t{:>10}: {}'.format('Memory', self.memory))
        print('\t{:>10}: {}'.format('Hard drive', self.hard_drive))
        print('\t{:>10}: {}'.format('Video card', self.video_card))


# abstract_builder.py

# from computer import Computer
from abc import ABC, abstractmethod

class AbsBuilder(ABC):

    def new_computer(self):
        self._computer = Computer()

    def get_computer(self):
        return self._computer

    @abstractmethod
    def build_mainboard(self):
        pass

    @abstractmethod
    def get_case(self):
        pass

    @abstractmethod
    def build_mainboard(self):
        pass

    @abstractmethod
    def install_mainboard(self):
        pass

    @abstractmethod
    def install_hard_drive(self):
        pass

    @abstractmethod
    def install_video_card(self):
        pass

# desktop_builder.py

# from abstract_builder import AbsBuilder

class DesktopBuilder(AbsBuilder):

    def get_case(self):
        self._computer.case = 'Coolermaster N300'
     
    def build_mainboard(self):
        self._computer.mainboard = 'MSI 970'
        self._computer.cpu = 'Intel Core i7-4770'
        self._computer.memory = 'Corsair Vengeance 16GB'

    def install_mainboard(self):
        pass

    def install_hard_drive(self):
        self._computer.hard_drive = 'Seagate 2TB'

    def install_video_card(self):
        self._computer.video_card = 'GeForce GTX 1070'


# directory.py

class Director:

    def __init__(self, builder):
        self._builder = builder

    def build_computer(self):
        self._builder.new_computer()
        self._builder.get_case()
        self._builder.build_mainboard()
        self._builder.install_mainboard()
        self._builder.install_hard_drive()
        self._builder.install_video_card()

    def get_computer(self):
        return self._builder.get_computer()

# main.py

# from director import Director
# from desktop_builder import DesktopBuilder

computer_builder = Director(DesktopBuilder())
computer_builder.build_computer()
computer = computer_builder.get_computer()
computer.display()


# laptop_builder.py

# from abstract_builder import AbsBuilder

class LaptopBuilder(AbsBuilder):

    def get_case(self):
        self._computer.case = 'IN WIN BP655'
     
    def build_mainboard(self):
        self._computer.mainboard = 'ASRock AM1H-ITX'
        self._computer.cpu = 'AMD Athlon 5150'
        self._computer.memory = 'Kingston ValueRAM 4GB'

    def install_mainboard(self):
        pass

    def install_hard_drive(self):
        self._computer.hard_drive = 'WD Blue 1TB'

    def install_video_card(self):
        self._computer.video_card = 'On board'


# main.py

# from director import Director
# from laptop_builder import LaptopBuilder

computer_builder = Director(LaptopBuilder())
computer_builder.build_computer()
computer = computer_builder.get_computer()
computer.display()
