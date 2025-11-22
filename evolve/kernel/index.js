//  main kernel file

const EvolveKernel = function () {
    // internal node mapping (maps NodeID --> DOM node)

    nodes = Map();
    let nextNodeID = 1;

    // callback registery for WASM/Python to register functions

    const callBacks = Map();
    let nextCallBackID = 1;

    // functions that give next callback and node id to assign
    function getNodeID(){return nextNodeID++;}
    function getCallBackID(){return nextCallBackID++;}

    // Logger
    // logs everything according to logging level and message provided
    function log(level,message){
        // create complete payload by adding TimeStamp 
        const payload = {ts: Date.now(), level, message};

        // if error exists, this becomes --> console.error("[kernel]",payload) or if not error this becomes --> onsole.log("[kernel]",payload)
        // Dynamic method selection
        console[level==="error"?"error":"log"]("[Kernel]",payload);

        return {ok: true};

    }

    // DOM helpers

    function create(tag,props={},children=[]){
        try{
            // creates HTML Element named tag
            const element = document.createElement(tag);
            // apply props to this created element
            applyProps(element,props);

            // generate new id for this element
            const id = getNodeID();
            // add new id and corresponding element to the nodes registery
            nodes.set(id,element)

            // also attach children if any, (children can be nodesIDs or strings)
            for (const child of children){
                // if child is number attach it as child of current element
                if (typeof(child)=== "number"){
                    // get the DOM element with this id
                    const childNode = nodes.get(child)

                    if (childNode){
                        element.appendChild(childNode)
                    }
                    else{
                        // child is string
                        element.appendChild(document.createTextNode(String(child)));

                    }
                }
            }
            return {ok: true, value: id};

        }catch(e){
            return {ok: false, error: e.message};
        }

    }

function applyProps(el,props){
    // Object.entries() turns object into array of [key,value] pairs
    for (const [k,v] of Object.entries(props)){

        // if prop is style, assign value (v) of style to element(i.e. assign each style to element, eg. element .style.color="red")
        if (k==="style" && typeof v==="object"){

            Object.assign(el.style,v)
        }
        else if(k.startsWith("on") && typeof v==="string"){
            // this means v is callback string from WASM/Python
            // We will attach an event listner that calls kernel.async.call(callBackID,[eventDATA])
            // removes "on" from "onClick" and gives "click" event
            const eventName = k.slice(2).toLowerCase();
            // convert callbackID from string to number
            const callBackID = Number(v)
            el.addEventListener(eventName, (ev)=>{
                const eventData = {type: ev.type, targetID: findNodeID(el)}

                asyncCall(callBackID,[eventData])
            })

        }else if(k==="textContent"){
            el.textContent = v;
        }
        else{
            el.setAttribute(k,v)
        }

    }
    
}







};
