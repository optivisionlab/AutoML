import { MarketplaceModelDetail } from "@/types/marketplace";

export default function Details({ model }: { model: MarketplaceModelDetail }) {
  return (
    <div className="space-y-10">
      {/* Overview */}
      <section>
        <h2 className="text-xl font-semibold mb-3">Tổng quan</h2>
        <p className="text-gray-700 leading-relaxed">{model.description}</p>
      </section>

      {/* Features */}
      <section>
        <h2 className="text-xl font-semibold mb-3">Tính năng</h2>
        <ul className="list-disc ml-6 space-y-1 text-gray-700">
          {model.features.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </section>

      {/* Specs */}
      <section>
        <h2 className="text-xl font-semibold mb-3">Thông số kỹ thuật</h2>
        <div className="border rounded-lg divide-y">
          {model.specs.map((spec) => (
            <div
              key={spec.label}
              className="flex justify-between px-4 py-3 text-sm"
            >
              <span className="text-gray-600">{spec.label}</span>
              <span className="font-medium text-gray-900">{spec.value}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Gói dịch vụ</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {model.pricing.map((plan) => (
            <div
              key={plan.name}
              className={`border rounded-lg p-5 ${
                plan.highlight ? "border-blue-600 shadow-md" : ""
              }`}
            >
              <h3 className="font-semibold">{plan.name}</h3>
              <p className="text-blue-600 text-lg font-bold mt-2">
                {plan.price}
              </p>
              <p className="text-sm text-gray-600 mt-2">{plan.description}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
