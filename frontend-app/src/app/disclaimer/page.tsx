export default function DisclaimerPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-3xl font-black mb-8">면책 조항</h1>
      <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-8 space-y-6 text-[#94a3b8] text-sm leading-relaxed">

        <section>
          <h2 className="text-lg font-bold text-white mb-3">1. 서비스 성격</h2>
          <p>본 서비스(&quot;KBO AI Analyzer&quot;)는 통계 데이터 및 인공지능 기반의 <strong className="text-white">스포츠 분석 정보</strong>를 제공하는 서비스입니다. 본 서비스는 경기 결과를 보장하거나 특정 행위를 권유하지 않으며, 제공되는 모든 분석 결과는 참고 자료로만 활용되어야 합니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">2. 분석 결과의 한계</h2>
          <ul className="list-disc pl-5 space-y-2">
            <li>본 서비스의 분석 결과는 과거 데이터와 통계 모델에 기반한 <strong className="text-white">확률적 추정</strong>이며, 실제 경기 결과와 일치하지 않을 수 있습니다.</li>
            <li>야구 경기는 본질적으로 불확실한 요소(선수 컨디션, 날씨, 심판 판정 등)가 많으며, 어떤 분석 모델도 이를 완벽히 예측할 수 없습니다.</li>
            <li>AI 에이전트의 토론 내용은 언어 모델의 생성물이며, 사실과 다른 정보가 포함될 수 있습니다.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">3. 금지 사항</h2>
          <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-4">
            <p className="text-red-300 font-semibold mb-2">본 서비스의 분석 정보를 다음 목적으로 사용하는 것을 엄격히 금지합니다:</p>
            <ul className="list-disc pl-5 space-y-1 text-red-300/80">
              <li>불법 도박 또는 사행 행위</li>
              <li>불법 스포츠 베팅</li>
              <li>기타 법률에 위반되는 행위</li>
            </ul>
          </div>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">4. 책임 제한</h2>
          <p>본 서비스 이용으로 발생하는 직접적, 간접적, 부수적, 특별, 결과적 손해에 대해 운영자는 어떠한 책임도 지지 않습니다. 이용자는 본 서비스의 분석 정보를 자신의 판단과 책임 하에 활용해야 합니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">5. 데이터 출처</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>경기 결과 및 일정: KBO 공식 사이트 (koreabaseball.com)</li>
            <li>선수 통계: 공개 데이터셋 (Kaggle, CC-BY-SA 라이선스)</li>
            <li>분석 모델: 자체 개발 ML 모델 (XGBoost, ELO, LightGBM)</li>
            <li>AI 분석: OpenAI GPT, Anthropic Claude API</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">6. 도움이 필요하신 분께</h2>
          <div className="bg-amber-950/20 border border-amber-900/30 rounded-lg p-4">
            <p className="text-amber-300">도박 문제로 어려움을 겪고 계신 분은 아래로 연락해 주세요.</p>
            <p className="text-amber-200 font-bold mt-2">한국도박문제관리센터: 1336 (24시간 무료 상담)</p>
          </div>
        </section>

        <p className="text-xs text-[#475569] pt-4 border-t border-[#1e293b]">
          본 면책 조항은 2026년 4월 1일부터 적용됩니다. 운영자는 본 조항을 사전 통지 없이 변경할 수 있습니다.
        </p>
      </div>
    </div>
  );
}
