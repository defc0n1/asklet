import os
import random
import re
import uuid
import yaml

from six.moves import input as raw_input
from six import string_types as basestring

from . import constants as c

def sterialize(s):
    s = re.sub('[^a-z0-9_]+', ' ', s.lower())
    s = s.strip().replace(' ', '_')
    return s

def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False
    except TypeError:
        return False

class BaseUser(object):
    """
    The interface the system expects when communicating with a user.
    """
    
    def __init__(self):
        self._target = None
        
    def think_of_something(self):
        """
        Randomly choices a target for the system to guess.
        """
        raise NotImplementedError
    
    @property
    def target(self):
        return self._target
        
    @target.setter
    def target(self, v):
        self._target = v
    
    def set_target_from_slug(self, slug):
        self.target = slug
    
    def ask(self, question_slug):
        """
        Returns the user's belief in the question's relation
        to our secret target.
        """
        raise NotImplementedError
    
    def is_it(self, target):
        """
        Confirms or denies whether or not the given target is the one we chose.
        """
        raise NotImplementedError
    
    def describe(self, n, exclude=set()):
        """
        Returns 3 random attributes of our target.
        """
        raise NotImplementedError

class MatrixUser(BaseUser):
    """
    An automated user whose knowledge is contained in a matrix.
    """
    
    def __init__(self, fn):
        super(BaseUser, self).__init__()
        self.data = {}
        
        # Convert raw matrix to Conceptnet format.
        data = yaml.load(open(fn))
        for target, questions in data.iteritems():
            target_slug = target
            if '/' not in target:
                target_slug = '/c/en/{name}/n/{name}'.format(name=target)
            self.data.setdefault(target_slug, {})
            for question, weight in questions.iteritems():
                question_slug = question
                if '/' not in question:
                    question_slug = '/r/IsA,/c/en/{name}/n/{name}'.format(name=question)
                self.data[target_slug][question_slug] = weight
        
    def think_of_something(self):
        """
        Randomly choices a target for the system to guess.
        """
        self.target = random.choice(list(self.data.keys()))
        
    def ask(self, question_slug):
        """
        Returns the user's belief in the question's relation
        to our secret target.
        """
        return self.data[self.target][question_slug]
    
    def is_it(self, target):
        """
        Confirms or denies whether or not the given target is the one we chose.
        """
        return self.target == target
    
    def describe(self, n, exclude=set()):
        """
        Returns 3 random attributes of our target.
        """
        attrs = set(self.data[self.target].keys())
        attrs = list(attrs.difference(exclude))
        random.shuffle(attrs)
        #Don't do this. Otherwise, we'll get the same hints over and over.
        #attrs = sorted(attrs, key=lambda k: self.data[self.target][k], reverse=True)
        attrs = attrs[:n]
        return [(_, self.data[self.target][_]) for _ in attrs]

class DomainUser(BaseUser):
    """
    An automated user whose knowledge is contained in a domain.
    Designed to test the accuracy of a domain by having the system play itself.
    """
    
    def __init__(self, domain):
        super(BaseUser, self).__init__()
        self.domain = domain
        assert domain.targets.all().count(), \
            'DomainUser requires a domain with at least one target.'
        
    def think_of_something(self):
        """
        Randomly choices a target for the system to guess.
        """
        # Note, unlike the MatrixUser, we store our target
        # as a Target model instance.
        self.target = self.domain.targets.all().order_by('?')[0]
        
    def set_target_from_slug(self, slug):
        self.target = self.domain.targets.filter(slug=slug)[0]
        
    def ask(self, question_slug):
        """
        Returns the user's belief in the question's relation
        to our secret target.
        """
        question = self.domain.questions.filter(slug=question_slug)[0]
        nweight = self.domain.get_weight(
            target=self.target,
            question=question,
            normalized=True)
        return nweight
    
    def is_it(self, target):
        """
        Confirms or denies whether or not the given target is the one we chose.
        """
        from .models import Target
        if isinstance(target, basestring):
            target = self.domain.targets.filter(slug=target)[0]
        assert isinstance(target, Target)
        return self.target == target
    
    def describe(self, n, exclude=set()):
        """
        Returns 3 random attributes of our target.
        """
        # There's no point in telling ourselves N things we already know.
        return []

class ShellUser(BaseUser):
    """
    A user interacting through a shell.
    """
    
    id_filename = '/tmp/asklet_user'
    
    def __init__(self, id=None):
        super(BaseUser, self).__init__()
        self.target = None
        self.id = id or str(uuid.uuid4()).replace('-', '')
        self.save()
    
    @classmethod
    def load(cls, clear=False):
        """
        Loads the locally saved user id.
        """
        id = None
        fn = cls.id_filename
        if not clear and os.path.isfile(fn):
            id = open(fn, 'r').read().strip()
        return cls(id=id)
    
    def clear(self):
        fn = self.id_filename
        if os.path.isfile(fn):
            os.remove(fn)
            
    def save(self):
        fn = self.id_filename
        open(fn, 'w').write(self.id)
    
    def think_of_something(self):
        """
        Randomly choices a target for the system to guess.
        """
        print('Think of something.')
        while 1:
            target = raw_input('Enter it here: ')
            target = sterialize(target)
            if target:
                break
            print('Sorry, but that string is invalid.')
            print('Please enter a simple non-empty string with no punctuation.')
        print('You are thinking of %s.' % target)
        self.target = target
    
    def set_target_from_slug(self, slug):
        # The shell user is an actual person, so we can't overide their choice.
        raise NotImplementedError, "Don't tell me what to do!"
        
    def ask(self, question_slug):
        """
        Returns the user's belief in the question's relation
        to our secret target.
        """
        while 1:
            print('%s? ' % question_slug)
            weight = raw_input('Enter integer weight between %s and %s: ' % (c.YES, c.NO))
            if is_int(weight):
                weight = int(weight)
                if c.YES >= weight >= c.NO:
                    return weight
            print('Sorry, but that weight is invalid.')
    
    def is_it(self, target):
        """
        Confirms or denies whether or not the given target is the one we chose.
        """
        while 1:
            print('%s?' % target)
            yn = raw_input('y/n: ').strip().lower()
            if yn.startswith('y'):
                return True
            elif yn.startswith('n'):
                return False
            print('Sorry, but that response is invalid.')
    
    def describe(self, n=3, exclude=set()):
        """
        Returns 3 random attributes of our target.
        """
        things = []
        assert n > 0
        print('Please describe %i things about this.' % n)
        while len(things) < n:
            response = raw_input('<thing> <weight>').strip()
            if not response:
                break
            #response = sterialize(response)
            parts = response.split(' ')
            if parts:
                weight = parts[-1]
                if is_int(weight):
                    weight = int(weight)
                    slug = '_'.join(parts[:-1])
                    things.append((slug, weight))
            print('Sorry, but that is an invalid input.')
        return things
    