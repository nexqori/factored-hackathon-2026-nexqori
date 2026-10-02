import type {Language} from './locales';
import {et,type EditorKey} from './editorLocales';
import type {Activation} from './workflowGraph';
import {Zap} from 'lucide-react';

export function ActivationPlan({items,language}:{items:Activation[];language:Language}){
 return <div className="activation-plan">{items.map((item,i)=><div className="activation-item" data-activation={item.id} key={item.node_id+item.id+i}>
  <span className="activation-badge"><Zap size={12}/>{et(language,'wouldActivate')}</span>
  <strong>{item.titles[language]}</strong>
  <details><summary>{et(language,'requirements')}</summary><ul>{item.requirements.map(required=><li key={required}>{et(language,required as EditorKey)}</li>)}</ul><code>{item.id}</code></details>
 </div>)}</div>;
}
