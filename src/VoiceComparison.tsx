import {useTranslation} from 'react-i18next';
import {formatMoney} from './components';
import type {Locale} from './i18n';
import type {ChatReply} from './AssistantPanel';

export function VoiceComparison({comparison}:{comparison:NonNullable<ChatReply['voiceSummary']>['comparison']}){
  const {t,i18n}=useTranslation();const locale=i18n.language as Locale;
  if(!comparison)return null;
  return <section className="voice-comparison" aria-label={t('voiceCall.comparison')}>
        <h3>{t('voiceCall.comparison')}</h3>
        {[{label:t(comparison.basis==='agreement'?'spending.conditionsBase':'spending.average'),value:comparison.baselineMinor},
          {label:t('voiceCall.currentAmount'),value:comparison.currentMinor}].map((bar,index)=><div key={index} className="voice-comparison-row">
          <div><span>{bar.label}</span><strong>{formatMoney(bar.value,locale,comparison.currency)}</strong></div>
          <span className={'voice-comparison-bar bar-'+index} style={{width:Math.max(2,100*bar.value/Math.max(1,comparison.baselineMinor,comparison.currentMinor))+'%'}} aria-hidden="true"/>
        </div>)}
        <p>{t('voiceCall.verdict.'+comparison.verdict)}</p>
      </section>;
}
