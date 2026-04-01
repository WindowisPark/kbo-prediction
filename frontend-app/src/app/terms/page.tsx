export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-3xl font-black mb-8">이용약관</h1>
      <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-8 space-y-6 text-[#94a3b8] text-sm leading-relaxed">

        <section>
          <h2 className="text-lg font-bold text-white mb-3">제1조 (목적)</h2>
          <p>본 약관은 KBO AI Analyzer(이하 &quot;서비스&quot;)의 이용과 관련하여 운영자와 이용자 간의 권리, 의무 및 책임사항을 규정함을 목적으로 합니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">제2조 (서비스의 정의)</h2>
          <p>본 서비스는 KBO 프로야구 경기에 대한 <strong className="text-white">통계 기반 데이터 분석 및 AI 분석 정보를 제공</strong>하는 스포츠 분석 플랫폼입니다. 본 서비스는 도박, 베팅 또는 사행 행위를 위한 서비스가 아닙니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">제3조 (이용자의 의무)</h2>
          <p>이용자는 다음 행위를 하여서는 안 됩니다:</p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>본 서비스의 분석 정보를 불법 도박 또는 사행 행위에 이용하는 행위</li>
            <li>서비스의 정상적 운영을 방해하는 행위</li>
            <li>타인의 정보를 도용하거나 허위 정보를 등록하는 행위</li>
            <li>서비스에서 제공하는 콘텐츠를 무단으로 복제, 배포하는 행위</li>
            <li>서비스를 상업적 목적으로 무단 이용하는 행위</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">제4조 (지적재산권)</h2>
          <p>서비스 내 분석 콘텐츠, AI 에이전트 토론 결과, 분석 모델 및 알고리즘에 대한 지적재산권은 운영자에게 귀속됩니다. 경기 결과, 선수 성적 등 사실 데이터는 공공 정보로서 별도의 권리 주장 대상이 아닙니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">제5조 (면책)</h2>
          <p>운영자는 분석 정보의 정확성, 완전성, 적시성을 보장하지 않으며, 이용자가 서비스를 통해 얻은 정보를 활용하여 발생한 손해에 대해 책임을 지지 않습니다. 자세한 사항은 <a href="/disclaimer" className="text-blue-400 underline">면책 조항</a>을 참고하세요.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">제6조 (서비스 변경 및 중단)</h2>
          <p>운영자는 운영상, 기술상의 사유로 서비스를 변경하거나 중단할 수 있습니다. 서비스 변경 또는 중단 시 사전에 공지하며, 불가피한 경우 사후에 공지할 수 있습니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">제7조 (분쟁 해결)</h2>
          <p>본 약관에 관한 분쟁은 대한민국 법률에 따르며, 관할 법원은 운영자의 소재지를 관할하는 법원으로 합니다.</p>
        </section>

        <p className="text-xs text-[#475569] pt-4 border-t border-[#1e293b]">
          시행일: 2026년 4월 1일
        </p>
      </div>
    </div>
  );
}
