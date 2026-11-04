export interface LicenseSection {
	heading?: string
	paragraphs: string[]
}

export interface LicenseText {
	title: string
	sections: LicenseSection[]
}

// Transcribed from the files in static/licenses; keep the wording identical to the originals.
export const QWEN_LICENSE: LicenseText = {
	title: 'Qwen Research License Agreement',
	sections: [
		{
			paragraphs: [
				'Qwen RESEARCH LICENSE AGREEMENT Release Date: September 19, 2024',
				'By clicking to agree or by using or distributing any portion or element of the Qwen Materials, you will be deemed to have recognized and accepted the content of this Agreement, which is effective immediately.',
			],
		},
		{
			heading: '1. Definitions',
			paragraphs: [
				'a. This Qwen RESEARCH LICENSE AGREEMENT (this "Agreement") shall mean the terms and conditions for use, reproduction, distribution and modification of the Materials as defined by this Agreement.',
				'b. "We" (or "Us") shall mean Alibaba Cloud.',
				'c. "You" (or "Your") shall mean a natural person or legal entity exercising the rights granted by this Agreement and/or using the Materials for any purpose and in any field of use.',
				'd. "Third Parties" shall mean individuals or legal entities that are not under common control with us or you.',
				'e. "Qwen" shall mean the large language models, and software and algorithms, consisting of trained model weights, parameters (including optimizer states), machine-learning model code, inference-enabling code, training-enabling code, fine-tuning enabling code and other elements of the foregoing distributed by us.',
				'f. "Materials" shall mean, collectively, Alibaba Cloud\'s proprietary Qwen and Documentation (and any portion thereof) made available under this Agreement.',
				'g. "Source" form shall mean the preferred form for making modifications, including but not limited to model source code, documentation source, and configuration files.',
				'h. "Object" form shall mean any form resulting from mechanical transformation or translation of a Source form, including but not limited to compiled object code, generated documentation, and conversions to other media types.',
				'i. "Non-Commercial" shall mean for research or evaluation purposes only.',
			],
		},
		{
			heading: '2. Grant of Rights',
			paragraphs: [
				"a. You are granted a non-exclusive, worldwide, non-transferable and royalty-free limited license under Alibaba Cloud's intellectual property or other rights owned by us embodied in the Materials to use, reproduce, distribute, copy, create derivative works of, and make modifications to the Materials FOR NON-COMMERCIAL PURPOSES ONLY.",
				'b. If you are commercially using the Materials, you shall request a license from us.',
			],
		},
		{
			heading: '3. Redistribution',
			paragraphs: [
				'You may distribute copies or make the Materials, or derivative works thereof, available as part of a product or service that contains any of them, with or without modifications, and in Source or Object form, provided that you meet the following conditions:',
				'a. You shall give any other recipients of the Materials or derivative works a copy of this Agreement;',
				'b. You shall cause any modified files to carry prominent notices stating that you changed the files;',
				'c. You shall retain in all copies of the Materials that you distribute the following attribution notices within a "Notice" text file distributed as a part of such copies: "Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) Alibaba Cloud. All Rights Reserved."; and',
				'd. You may add your own copyright statement to your modifications and may provide additional or different license terms and conditions for use, reproduction, or distribution of your modifications, or for any such derivative works as a whole, provided your use, reproduction, and distribution of the work otherwise complies with the terms and conditions of this Agreement.',
			],
		},
		{
			heading: '4. Rules of use',
			paragraphs: [
				'a. The Materials may be subject to export controls or restrictions in China, the United States or other countries or regions. You shall comply with applicable laws and regulations in your use of the Materials.',
				'b. If you use the Materials or any outputs or results therefrom to create, train, fine-tune, or improve an AI model that is distributed or made available, you shall prominently display “Built with Qwen” or “Improved using Qwen” in the related product documentation.',
			],
		},
		{
			heading: '5. Intellectual Property',
			paragraphs: [
				'a. We retain ownership of all intellectual property rights in and to the Materials and derivatives made by or for us. Conditioned upon compliance with the terms and conditions of this Agreement, with respect to any derivative works and modifications of the Materials that are made by you, you are and will be the owner of such derivative works and modifications.',
				'b. No trademark license is granted to use the trade names, trademarks, service marks, or product names of us, except as required to fulfill notice requirements under this Agreement or as required for reasonable and customary use in describing and redistributing the Materials.',
				'c. If you commence a lawsuit or other proceedings (including a cross-claim or counterclaim in a lawsuit) against us or any entity alleging that the Materials or any output therefrom, or any part of the foregoing, infringe any intellectual property or other right owned or licensable by you, then all licenses granted to you under this Agreement shall terminate as of the date such lawsuit or other proceeding is commenced or brought.',
			],
		},
		{
			heading: '6. Disclaimer of Warranty and Limitation of Liability',
			paragraphs: [
				'a. We are not obligated to support, update, provide training for, or develop any further version of the Qwen Materials or to grant any license thereto.',
				'b. THE MATERIALS ARE PROVIDED "AS IS" WITHOUT ANY EXPRESS OR IMPLIED WARRANTY OF ANY KIND INCLUDING WARRANTIES OF MERCHANTABILITY, NONINFRINGEMENT, OR FITNESS FOR A PARTICULAR PURPOSE. WE MAKE NO WARRANTY AND ASSUME NO RESPONSIBILITY FOR THE SAFETY OR STABILITY OF THE MATERIALS AND ANY OUTPUT THEREFROM.',
				'c. IN NO EVENT SHALL WE BE LIABLE TO YOU FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO ANY DIRECT, OR INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES ARISING FROM YOUR USE OR INABILITY TO USE THE MATERIALS OR ANY OUTPUT OF IT, NO MATTER HOW IT’S CAUSED.',
				'd. You will defend, indemnify and hold harmless us from and against any claim by any third party arising out of or related to your use or distribution of the Materials.',
			],
		},
		{
			heading: '7. Survival and Termination.',
			paragraphs: [
				'a. The term of this Agreement shall commence upon your acceptance of this Agreement or access to the Materials and will continue in full force and effect until terminated in accordance with the terms and conditions herein.',
				'b. We may terminate this Agreement if you breach any of the terms or conditions of this Agreement. Upon termination of this Agreement, you must delete and cease use of the Materials. Sections 6 and 8 shall survive the termination of this Agreement.',
			],
		},
		{
			heading: '8. Governing Law and Jurisdiction.',
			paragraphs: [
				'a. This Agreement and any dispute arising out of or relating to it will be governed by the laws of China, without regard to conflict of law principles, and the UN Convention on Contracts for the International Sale of Goods does not apply to this Agreement.',
				"b. The People's Courts in Hangzhou City shall have exclusive jurisdiction over any dispute arising out of this Agreement.",
			],
		},
		{
			heading: '9. Other Terms and Conditions.',
			paragraphs: [
				'a. Any arrangements, understandings, or agreements regarding the Material not stated herein are separate from and independent of the terms and conditions of this Agreement. You shall request a separate license from us, if you use the Materials in ways not expressly agreed to in this Agreement.',
				'b. We shall not be bound by any additional or different terms or conditions communicated by you unless expressly agreed.',
			],
		},
	],
}

export const NVIDIA_LICENSE: LicenseText = {
	title: 'NVIDIA License',
	sections: [
		{
			heading: '1. Definitions',
			paragraphs: [
				'“Licensor” means any person or entity that distributes its Work.',
				'“Work” means (a) the original work of authorship made available under this license, which may include software, documentation, or other files, and (b) any additions to or derivative works thereof that are made available under this license.',
				'The terms “reproduce,” “reproduction,” “derivative works,” and “distribution” have the meaning as provided under U.S. copyright law; provided, however, that for the purposes of this license, derivative works shall not include works that remain separable from, or merely link (or bind by name) to the interfaces of, the Work.',
				'Works are “made available” under this license by including in or with the Work either (a) a copyright notice referencing the applicability of this license to the Work, or (b) a copy of this license.',
			],
		},
		{
			heading: '2. License Grant',
			paragraphs: [
				'2.1 Copyright Grant. Subject to the terms and conditions of this license, each Licensor grants to you a perpetual, worldwide, non-exclusive, royalty-free, copyright license to use, reproduce, prepare derivative works of, publicly display, publicly perform, sublicense and distribute its Work and any resulting derivative works in any form.',
			],
		},
		{
			heading: '3. Limitations',
			paragraphs: [
				'3.1 Redistribution. You may reproduce or distribute the Work only if (a) you do so under this license, (b) you include a complete copy of this license with your distribution, and (c) you retain without modification any copyright, patent, trademark, or attribution notices that are present in the Work.',
				'3.2 Derivative Works. You may specify that additional or different terms apply to the use, reproduction, and distribution of your derivative works of the Work (“Your Terms”) only if (a) Your Terms provide that the use limitation in Section 3.3 applies to your derivative works, and (b) you identify the specific derivative works that are subject to Your Terms. Notwithstanding Your Terms, this license (including the redistribution requirements in Section 3.1) will continue to apply to the Work itself.',
				'3.3 Use Limitation. The Work and any derivative works thereof only may be used or intended for use non-commercially. Notwithstanding the foregoing, NVIDIA Corporation and its affiliates may use the Work and any derivative works commercially. As used herein, “non-commercially” means for academic purposes only.',
				'3.4 Patent Claims. If you bring or threaten to bring a patent claim against any Licensor (including any claim, cross-claim or counterclaim in a lawsuit) to enforce any patents that you allege are infringed by any Work, then your rights under this license from such Licensor (including the grant in Section 2.1) will terminate immediately.',
				'3.5 Trademarks. This license does not grant any rights to use any Licensor’s or its affiliates’ names, logos, or trademarks, except as necessary to reproduce the notices described in this license.',
				'3.6 Termination. If you violate any term of this license, then your rights under this license (including the grant in Section 2.1) will terminate immediately.',
			],
		},
		{
			heading: '4. Disclaimer of Warranty.',
			paragraphs: [
				'THE WORK IS PROVIDED “AS IS” WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING WARRANTIES OR CONDITIONS OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE OR NON-INFRINGEMENT. YOU BEAR THE RISK OF UNDERTAKING ANY ACTIVITIES UNDER THIS LICENSE.',
			],
		},
		{
			heading: '5. Limitation of Liability.',
			paragraphs: [
				'EXCEPT AS PROHIBITED BY APPLICABLE LAW, IN NO EVENT AND UNDER NO LEGAL THEORY, WHETHER IN TORT (INCLUDING NEGLIGENCE), CONTRACT, OR OTHERWISE SHALL ANY LICENSOR BE LIABLE TO YOU FOR DAMAGES, INCLUDING ANY DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES ARISING OUT OF OR RELATED TO THIS LICENSE, THE USE OR INABILITY TO USE THE WORK (INCLUDING BUT NOT LIMITED TO LOSS OF GOODWILL, BUSINESS INTERRUPTION, LOST PROFITS OR DATA, COMPUTER FAILURE OR MALFUNCTION, OR ANY OTHER DAMAGES OR LOSSES), EVEN IF THE LICENSOR HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.',
			],
		},
	],
}
