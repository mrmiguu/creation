"""
Pythonic dom builders for Evolve
"""

from collections.abc import Callable
from ..kernel import kernel


class Element:
    """
    Represents DOM nodes created via kernel
    """
    
    def __init__(self, tag:str, props:dict[str:any], children:list[any]):
        self.tag = tag
        self.props = props
        self.children = children
        self.node_id:int | None=None
        
    def _build(self)->int:
        
        """
        create element in JS via kernel
        """        
        
        if self.node_id is not None:
            return self.node_id
        
        # process children (convert elements --> node_ids)
        preprocessed_children: list[any] = []
        
        for child in self.children:
            
            if isinstance(child,Element):
                child_id = child._build()
                preprocessed_children.append(child_id)
                
            else:
                preprocessed_children.append(child)
                
        # preprocess props: handle callbacks
        final_props: dict[str,any] = {}
        
        for k,v in self.props.items():
            if k.startswith("on") and callable(v):
                cb_id = kernel.register_callback(v)
                final_props[k] = str(cb_id)
            else:
                final_props[k] = v
                
        # create node
        res = kernel.dom.create(self.tag,final_props, preprocessed_children)
        if not res.get("ok"):
            raise RuntimeError(f"DOM create failed:{res.get('error')}")
        
        self.node_id=res.get("value")
        return self.node_id
    
    
#FACTORY FUNCTIONS
    
def _make_element(tag:str,*children:any ,**props:any, )->Element:
    return Element(tag,props, list(children))
        
                
def div(*children, **props) -> Element:
    return _make_element("div", *children, **props)

def button(*children, **props) -> Element:
    return _make_element("button", *children, **props)

def span(*children, **props) -> Element:
    return _make_element("span", *children, **props)

def p(*children, **props) -> Element:
    return _make_element("p", *children, **props)

def h1(*children, **props) -> Element:
    return _make_element("h1", *children, **props)

def input(*children, **props) -> Element:
    return _make_element("input", *children, **props)

def img(*children, **props) -> Element:
    return _make_element("img", *children, **props)


# MOUNT FUNCTION


def mount(element:Element, selector:str="#app"):
    """
    Mounts Python element under the selector
    
    """
    
    parent = kernel.dom.query(selector)
    
    if not parent.get("ok"):
        raise RuntimeError(f"Query failed:{parent.get('error')}")
    parent_id = parent["value"]
    if parent_id is None:
        raise RuntimeError(f"No DOM element matches {selector}")
    node_id = element._build()
    kernel.dom.append(parent_id,node_id)
    
