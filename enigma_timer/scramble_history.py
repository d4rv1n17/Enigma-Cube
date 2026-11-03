"""Per-session scramble navigation, independent of recorded solve history."""
from dataclasses import dataclass,field


@dataclass
class _Timeline:
    items:list=field(default_factory=list)
    position:int=-1


class ScrambleHistory:
    def __init__(self,limit=100):
        self.limit=limit
        self._sessions={}

    def _timeline(self,session_id):
        return self._sessions.setdefault(session_id,_Timeline())

    def current(self,session_id):
        t=self._timeline(session_id)
        return t.items[t.position] if t.position>=0 else None

    def can_previous(self,session_id):
        return self._timeline(session_id).position>0

    def can_next(self,session_id):
        t=self._timeline(session_id)
        return t.position<len(t.items)-1

    def previous(self,session_id):
        t=self._timeline(session_id)
        if t.position>0:
            t.position-=1
        return self.current(session_id)

    def next(self,session_id,generate,fresh=False):
        t=self._timeline(session_id)
        if not fresh and self.can_next(session_id):
            t.position+=1
        else:
            # An actual completed solve starts a fresh branch. Browsing the
            # forward history must not count as generating a new scramble.
            value=generate()
            del t.items[t.position+1:]
            t.items.append(value)
            if len(t.items)>self.limit:
                del t.items[:len(t.items)-self.limit]
            t.position=len(t.items)-1
        return self.current(session_id)
