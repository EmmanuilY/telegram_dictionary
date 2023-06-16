from model.db import DB

db = DB()


class LearningProcess:
    def __init__(self, user_id: str, type_of_words: str, number_of_words: int, type_of_learning: str):
        self.user_id = user_id
        self.type_of_words = type_of_words
        self.number_of_words = number_of_words
        self.type_of_learning = type_of_learning
        self.words = {}

    async def get_words(self,) -> dict:
        terms = await db.get_words(self.user_id, self.type_of_words, self.number_of_words, self.type_of_learning)
        return terms

    async def pre_learn(self):
        pass

    async def step1(self):
        pass

    async def step2(self):
        pass

    async def step3(self):
        pass

    async def final(self):
        pass


class LearningWords(LearningProcess):
    async def pre_pre_learn(self):
        pass

    async def final(self):
        pass


class RepeatTerms(LearningProcess):

    async def final(self):
        pass


class RepeatLearnedWords(LearningProcess):

    async def step1(self):
        pass

    async def step2(self):
        pass

    async def final(self):
        pass
